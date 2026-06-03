"""Best-effort live sync of inbox conversations/messages to Google Sheets."""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.integrations.google_sheets.client import (
    GoogleSheetsClient,
    GoogleSheetsNotConfigured,
)
from app.integrations.llm.client import get_llm_client
from app.models.company import Company
from app.models.company_config import CompanyConfig
from app.models.conversation import Conversation
from app.models.google_sheet_sync_job import GoogleSheetSyncJob
from app.models.message import Message
from app.repositories.company_config_repository import CompanyConfigRepository
from app.repositories.company_repository import CompanyRepository
from app.repositories.conversation_repository import ConversationRepository
from app.repositories.message_repository import MessageRepository

logger = logging.getLogger(__name__)

LEADS_HEADERS = [
    "ph no",
    "conversations (last 10 user messages)",
    "summary",
    "lead-type",
]


class GoogleSheetsSyncService:
    def __init__(self, db: AsyncSession, client: Optional[GoogleSheetsClient] = None) -> None:
        self._db = db
        self._client = client or GoogleSheetsClient()

    async def sync_message_best_effort(
        self,
        *,
        message: Message,
        conversation: Optional[Conversation] = None,
    ) -> None:
        try:
            await self.drain_due_jobs_best_effort()
            await self.sync_message(message=message, conversation=conversation)
        except GoogleSheetsNotConfigured as exc:
            logger.info("Google Sheets sync skipped", extra={"reason": str(exc)})
        except httpx.HTTPError as exc:
            if self._is_retryable(exc):
                await self._enqueue_job(
                    company_id=message.company_id,
                    job_type="message",
                    entity_id=message.id,
                    error=exc,
                )
            else:
                logger.info("Google Sheets sync skipped", extra={"reason": str(exc)})
        except Exception as exc:  # pragma: no cover - external integration guard
            logger.warning(
                "Google Sheets sync failed",
                extra={"message_id": str(message.id), "error": str(exc)},
                exc_info=True,
            )

    async def sync_conversation_best_effort(self, conversation: Conversation) -> None:
        try:
            await self.drain_due_jobs_best_effort()
            await self.sync_conversation(conversation)
        except GoogleSheetsNotConfigured as exc:
            logger.info("Google Sheets sync skipped", extra={"reason": str(exc)})
        except httpx.HTTPError as exc:
            if self._is_retryable(exc):
                await self._enqueue_job(
                    company_id=conversation.company_id,
                    job_type="conversation",
                    entity_id=conversation.id,
                    error=exc,
                )
            else:
                logger.info("Google Sheets sync skipped", extra={"reason": str(exc)})
        except Exception as exc:  # pragma: no cover - external integration guard
            logger.warning(
                "Google Sheets conversation sync failed",
                extra={"conversation_id": str(conversation.id), "error": str(exc)},
                exc_info=True,
            )

    async def sync_message(
        self,
        *,
        message: Message,
        conversation: Optional[Conversation] = None,
    ) -> None:
        if not settings.google_sheets_sync_enabled or not self._client.is_configured:
            return
        if conversation is None:
            conversation = await ConversationRepository(self._db).get(message.conversation_id)
        if conversation is None:
            return
        config = await CompanyConfigRepository(self._db).get_by_company(message.company_id)
        if not self._company_sync_enabled(config):
            return
        company = await CompanyRepository(self._db).get(message.company_id)
        spreadsheet_id = await self._ensure_sheet(config, company)
        if not spreadsheet_id:
            return
        await self._ensure_headers(spreadsheet_id)
        await self._upsert_lead(spreadsheet_id, conversation)

    async def sync_conversation(self, conversation: Conversation) -> None:
        if not settings.google_sheets_sync_enabled or not self._client.is_configured:
            return
        config = await CompanyConfigRepository(self._db).get_by_company(conversation.company_id)
        if not self._company_sync_enabled(config):
            return
        company = await CompanyRepository(self._db).get(conversation.company_id)
        spreadsheet_id = await self._ensure_sheet(config, company)
        if not spreadsheet_id:
            return
        await self._ensure_headers(spreadsheet_id)
        await self._upsert_lead(spreadsheet_id, conversation)

    async def provision_company_sheet(self, company_id: uuid.UUID) -> Optional[dict[str, str]]:
        if not settings.google_sheets_sync_enabled or not self._client.is_configured:
            return None
        config = await CompanyConfigRepository(self._db).get_by_company(company_id)
        if not self._company_sync_enabled(config):
            return None
        company = await CompanyRepository(self._db).get(company_id)
        spreadsheet_id = await self._ensure_sheet(config, company)
        if not spreadsheet_id:
            return None
        await self._ensure_headers(spreadsheet_id)
        return {
            "company_id": str(company_id),
            "spreadsheet_id": spreadsheet_id,
            "spreadsheet_url": config.google_sheet_url
            or GoogleSheetsClient.spreadsheet_url(spreadsheet_id),
        }

    async def drain_due_jobs_best_effort(self) -> None:
        try:
            await self.drain_due_jobs()
        except (GoogleSheetsNotConfigured, httpx.HTTPError) as exc:
            logger.info("Google Sheets retry drain skipped", extra={"reason": str(exc)})
        except Exception as exc:  # pragma: no cover - external integration guard
            logger.warning(
                "Google Sheets retry drain failed",
                extra={"error": str(exc)},
                exc_info=True,
            )

    async def drain_due_jobs(self) -> int:
        if not settings.google_sheets_sync_enabled or not self._client.is_configured:
            return 0
        now = datetime.now(timezone.utc)
        result = await self._db.execute(
            select(GoogleSheetSyncJob)
            .where(
                GoogleSheetSyncJob.status == "pending",
                GoogleSheetSyncJob.next_attempt_at <= now,
            )
            .order_by(GoogleSheetSyncJob.next_attempt_at, GoogleSheetSyncJob.created_at)
            .limit(max(1, settings.google_sheets_retry_batch_size))
        )
        jobs = list(result.scalars().all())
        processed = 0
        for job in jobs:
            try:
                await self._run_job(job)
                job.status = "done"
                job.last_error = None
                processed += 1
            except GoogleSheetsNotConfigured:
                raise
            except httpx.HTTPError as exc:
                if self._is_retryable(exc):
                    self._schedule_retry(job, exc)
                else:
                    job.status = "failed"
                    job.last_error = str(exc)[:2000]
                processed += 1
            except Exception as exc:  # pragma: no cover - defensive outbox guard
                self._schedule_retry(job, exc)
                processed += 1
        await self._db.flush()
        return processed

    async def _run_job(self, job: GoogleSheetSyncJob) -> None:
        if job.job_type == "message":
            message = await self._db.get(Message, job.entity_id)
            if message is None:
                job.status = "failed"
                job.last_error = "Message no longer exists."
                return
            conversation = await ConversationRepository(self._db).get(message.conversation_id)
            await self.sync_message(message=message, conversation=conversation)
            return
        if job.job_type == "conversation":
            conversation = await ConversationRepository(self._db).get(job.entity_id)
            if conversation is None:
                job.status = "failed"
                job.last_error = "Conversation no longer exists."
                return
            await self.sync_conversation(conversation)
            return
        job.status = "failed"
        job.last_error = f"Unknown job_type {job.job_type!r}."

    async def _enqueue_job(
        self,
        *,
        company_id: uuid.UUID,
        job_type: str,
        entity_id: uuid.UUID,
        error: Exception,
    ) -> None:
        existing = await self._db.execute(
            select(GoogleSheetSyncJob)
            .where(
                GoogleSheetSyncJob.job_type == job_type,
                GoogleSheetSyncJob.entity_id == entity_id,
                GoogleSheetSyncJob.status == "pending",
            )
            .limit(1)
        )
        job = existing.scalar_one_or_none()
        if job is None:
            job = GoogleSheetSyncJob(
                company_id=company_id,
                job_type=job_type,
                entity_id=entity_id,
                payload_json={},
                status="pending",
                attempts=0,
                next_attempt_at=datetime.now(timezone.utc),
            )
            self._db.add(job)
            await self._db.flush()
        self._schedule_retry(job, error)
        await self._db.flush()
        logger.info(
            "Queued Google Sheets sync retry",
            extra={
                "job_type": job_type,
                "entity_id": str(entity_id),
                "attempts": job.attempts,
                "next_attempt_at": job.next_attempt_at.isoformat(),
            },
        )

    @staticmethod
    def _company_sync_enabled(config: Optional[CompanyConfig]) -> bool:
        return bool(config and getattr(config, "google_sheets_enabled", True))

    async def _ensure_sheet(
        self,
        config: Optional[CompanyConfig],
        company: Optional[Company],
    ) -> Optional[str]:
        if config is None:
            return None
        if config.google_sheet_id:
            if not config.google_sheet_url:
                config.google_sheet_url = GoogleSheetsClient.spreadsheet_url(config.google_sheet_id)
                await self._db.flush()
            return config.google_sheet_id
        if not settings.google_sheets_create_spreadsheets:
            return None
        title = f"{company.display_name if company else config.company_id} - Mindorax Live Inbox"
        spreadsheet_id, spreadsheet_url = await self._client.create_spreadsheet(title)
        config.google_sheet_id = spreadsheet_id
        config.google_sheet_url = spreadsheet_url
        await self._db.flush()
        return spreadsheet_id

    async def _ensure_headers(self, spreadsheet_id: str) -> None:
        await self._ensure_sheet_tabs(spreadsheet_id)
        await self._client.update_values(spreadsheet_id, "Leads!A1:D1", [LEADS_HEADERS])

    async def _ensure_sheet_tabs(self, spreadsheet_id: str) -> None:
        titles = await self._client.get_sheet_titles(spreadsheet_id)
        if "Leads" not in titles:
            await self._client.add_sheet(spreadsheet_id, "Leads")

    async def _upsert_lead(
        self,
        spreadsheet_id: str,
        conversation: Conversation,
    ) -> None:
        ids = await self._client.get_values(spreadsheet_id, "Leads!A2:A")
        target = conversation.customer_phone
        row_number: Optional[int] = None
        for idx, row in enumerate(ids, start=2):
            if row and str(row[0]) == target:
                row_number = idx
                break
        values = [await self._lead_row(conversation)]
        if row_number is None:
            await self._client.append_values(spreadsheet_id, "Leads!A:D", values)
        else:
            await self._client.update_values(
                spreadsheet_id, f"Leads!A{row_number}:D{row_number}", values
            )

    @staticmethod
    def _is_retryable(exc: httpx.HTTPError) -> bool:
        if isinstance(exc, httpx.HTTPStatusError):
            return exc.response.status_code in {429, 500, 502, 503, 504}
        return isinstance(exc, httpx.RequestError)

    @staticmethod
    def _retry_after_seconds(exc: Exception) -> Optional[int]:
        if isinstance(exc, httpx.HTTPStatusError):
            raw = exc.response.headers.get("Retry-After")
            if raw and raw.isdigit():
                return max(1, int(raw))
        return None

    def _schedule_retry(self, job: GoogleSheetSyncJob, exc: Exception) -> None:
        job.attempts += 1
        job.last_error = str(exc)[:2000]
        if job.attempts >= settings.google_sheets_retry_max_attempts:
            job.status = "failed"
            return
        retry_after = self._retry_after_seconds(exc)
        if retry_after is None:
            retry_after = settings.google_sheets_retry_base_seconds * (2 ** max(job.attempts - 1, 0))
        job.next_attempt_at = datetime.now(timezone.utc) + timedelta(seconds=retry_after)

    async def _lead_row(self, conversation: Conversation) -> list[Any]:
        preview = await self.lead_preview_row(conversation)
        return [
            preview["customer_phone"],
            preview["conversations_last_10_user_messages"],
            preview["summary"],
            preview["lead_type"],
        ]

    async def lead_preview_row(self, conversation: Conversation) -> dict[str, Any]:
        summary = await self.ensure_lead_summary(conversation)
        return {
            "conversation_id": conversation.id,
            "customer_phone": conversation.customer_phone,
            "conversations_last_10_user_messages": await self._last_customer_messages(conversation.id),
            "summary": summary,
            "lead_type": conversation.lead_warmth or "cold",
            "last_message_at": conversation.last_message_at,
            "inquiry_complete": bool(getattr(conversation, "inquiry_complete", False)),
        }

    async def ensure_lead_summary(self, conversation: Conversation) -> str:
        existing = (getattr(conversation, "lead_summary", None) or "").strip()
        summary_updated_at = getattr(conversation, "lead_summary_updated_at", None)
        last_message_at = getattr(conversation, "last_message_at", None)
        if existing and summary_updated_at is not None:
            if last_message_at is None or summary_updated_at >= last_message_at:
                return existing

        summary = await self._customer_need_summary(conversation.id)
        now = datetime.now(timezone.utc)
        conversation.lead_summary = summary
        conversation.lead_summary_updated_at = now
        await self._db.flush()
        return summary

    async def preview_rows(
        self,
        company_id: uuid.UUID,
        *,
        limit: int = 200,
        offset: int = 0,
        inquiry_filter: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        conversations = await ConversationRepository(self._db).list_for_inbox(
            company_id,
            limit=limit,
            offset=offset,
            inquiry_filter=inquiry_filter,
        )
        rows: list[dict[str, Any]] = []
        for conversation in conversations:
            rows.append(await self.lead_preview_row(conversation))
        return rows

    async def _last_customer_messages(self, conversation_id: uuid.UUID) -> str:
        msgs = await MessageRepository(self._db).list_recent_customer_messages(
            conversation_id,
            limit=10,
        )
        chunks: list[str] = []
        for msg in msgs:
            text = (msg.message_text or "").strip()
            if not text:
                continue
            if len(text) > 300:
                text = text[:300].rstrip() + "..."
            chunks.append(text)
        return "\n".join(chunks)

    async def _customer_need_summary(self, conversation_id: uuid.UUID) -> str:
        msgs = await MessageRepository(self._db).list_recent_customer_messages(
            conversation_id,
            limit=10,
        )
        chunks: list[str] = []
        for msg in msgs:
            text = (msg.message_text or "").strip()
            if not text:
                continue
            if len(text) > 220:
                text = text[:220].rstrip() + "..."
            chunks.append(text)
        if not chunks:
            return "No customer need captured yet."
        if len(chunks) == 1:
            return chunks[0]
        fallback = " | ".join(chunks[-3:])
        try:
            llm = get_llm_client()
            transcript = "\n".join(f"- {text}" for text in chunks)
            summary = await llm.generate_answer(
                context_chunks=[transcript],
                user_query=(
                    "Summarize this customer's need for a CRM/Google Sheet lead row. "
                    "Return one concise sentence only. Mention the main concern, desired product/help, "
                    "and urgency if clear. Do not add greetings, bullets, markdown, or invented details."
                ),
                system_prompt=(
                    "You create short CRM lead summaries from customer WhatsApp messages. "
                    "Use only the provided messages. Keep it under 160 characters."
                ),
                output_language="english",
                conversation_history=None,
            )
            summary = " ".join((summary or "").strip().split())
            if summary:
                return summary[:240]
        except Exception as exc:
            logger.info(
                "AI sheet summary failed; using fallback summary",
                extra={"conversation_id": str(conversation_id), "error": str(exc)},
            )
        return fallback
