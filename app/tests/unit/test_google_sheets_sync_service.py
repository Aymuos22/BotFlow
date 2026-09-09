import pytest


@pytest.fixture(autouse=True)
def _google_sheets_test_settings():
    from app.core.config import settings

    old_create = settings.google_sheets_create_spreadsheets
    old_enabled = settings.google_sheets_sync_enabled
    settings.google_sheets_create_spreadsheets = True
    settings.google_sheets_sync_enabled = True
    yield
    settings.google_sheets_create_spreadsheets = old_create
    settings.google_sheets_sync_enabled = old_enabled


class FakeSheetsClient:
    is_configured = True

    def __init__(self) -> None:
        self.updated: list[tuple[str, str, list[list[object]]]] = []
        self.appended: list[tuple[str, str, list[list[object]]]] = []
        self.created_titles: list[str] = []
        self.added_sheets: list[str] = []
        self.sheet_titles: set[str] = {"Leads"}

    async def create_spreadsheet(self, title: str) -> tuple[str, str]:
        self.created_titles.append(title)
        return "sheet123", "https://docs.google.com/spreadsheets/d/sheet123/edit"

    async def update_values(
        self,
        spreadsheet_id: str,
        range_name: str,
        values: list[list[object]],
    ) -> None:
        self.updated.append((spreadsheet_id, range_name, values))

    async def append_values(
        self,
        spreadsheet_id: str,
        range_name: str,
        values: list[list[object]],
    ) -> None:
        self.appended.append((spreadsheet_id, range_name, values))

    async def get_values(self, spreadsheet_id: str, range_name: str) -> list[list[object]]:
        return []

    async def get_sheet_titles(self, spreadsheet_id: str) -> set[str]:
        return set(self.sheet_titles)

    async def add_sheet(self, spreadsheet_id: str, title: str) -> None:
        self.added_sheets.append(title)
        self.sheet_titles.add(title)


class FlakySheetsClient(FakeSheetsClient):
    def __init__(self) -> None:
        super().__init__()
        self.fail_next_update = True

    async def update_values(
        self,
        spreadsheet_id: str,
        range_name: str,
        values: list[list[object]],
    ) -> None:
        if self.fail_next_update:
            self.fail_next_update = False
            import httpx

            request = httpx.Request("PUT", "https://sheets.googleapis.com/test")
            response = httpx.Response(
                429,
                request=request,
                headers={"Retry-After": "1"},
            )
            raise httpx.HTTPStatusError("quota exceeded", request=request, response=response)
        await super().update_values(spreadsheet_id, range_name, values)


@pytest.mark.asyncio
async def test_google_sheets_sync_creates_sheet_and_writes_message(
    db_session, sample_company_id
):
    from app.models.conversation import Conversation
    from app.models.message import Message
    from app.repositories.company_config_repository import CompanyConfigRepository
    from app.services.google_sheets_sync_service import GoogleSheetsSyncService

    conv = Conversation(
        company_id=sample_company_id,
        customer_phone="+919999999999",
        current_mode="bot",
        status="active",
    )
    db_session.add(conv)
    await db_session.flush()
    await db_session.refresh(conv)

    msg = Message(
        conversation_id=conv.id,
        company_id=sample_company_id,
        sender_type="customer",
        message_text="hello",
        language="english",
        external_message_id="wamid.test",
    )
    db_session.add(msg)
    await db_session.flush()
    await db_session.refresh(msg)

    fake = FakeSheetsClient()
    await GoogleSheetsSyncService(db_session, client=fake).sync_message(
        message=msg,
        conversation=conv,
    )

    config = await CompanyConfigRepository(db_session).get_by_company(sample_company_id)
    assert config is not None
    assert config.google_sheet_id == "sheet123"
    assert fake.created_titles == ["Test Company - BotFlow Live Inbox"]
    assert ("sheet123", "Leads!A:D") == fake.appended[0][:2]
    assert fake.appended[0][2][0] == [
        "+919999999999",
        "hello",
        "hello",
        "cold",
    ]


@pytest.mark.asyncio
async def test_google_sheets_sync_queues_retry_and_drains(db_session, sample_company_id):
    from datetime import datetime, timezone

    from sqlalchemy import select

    from app.models.conversation import Conversation
    from app.models.google_sheet_sync_job import GoogleSheetSyncJob
    from app.models.message import Message
    from app.services.google_sheets_sync_service import GoogleSheetsSyncService

    conv = Conversation(
        company_id=sample_company_id,
        customer_phone="+919999999999",
        current_mode="bot",
        status="active",
    )
    db_session.add(conv)
    await db_session.flush()
    await db_session.refresh(conv)

    msg = Message(
        conversation_id=conv.id,
        company_id=sample_company_id,
        sender_type="customer",
        message_text="retry me",
    )
    db_session.add(msg)
    await db_session.flush()
    await db_session.refresh(msg)

    fake = FlakySheetsClient()
    svc = GoogleSheetsSyncService(db_session, client=fake)
    await svc.sync_message_best_effort(message=msg, conversation=conv)

    queued = (
        await db_session.execute(select(GoogleSheetSyncJob).where(GoogleSheetSyncJob.status == "pending"))
    ).scalar_one()
    assert queued.job_type == "message"
    assert queued.entity_id == msg.id
    assert queued.attempts == 1

    queued.next_attempt_at = datetime.now(timezone.utc)
    await db_session.flush()
    drained = await svc.drain_due_jobs()
    assert drained == 1
    await db_session.refresh(queued)
    assert queued.status == "done"
    assert any(call[1] == "Leads!A:D" for call in fake.appended)


@pytest.mark.asyncio
async def test_google_sheets_sync_adds_leads_tab_when_missing(
    db_session, sample_company_id
):
    from app.models.conversation import Conversation
    from app.models.message import Message
    from app.services.google_sheets_sync_service import GoogleSheetsSyncService

    conv = Conversation(
        company_id=sample_company_id,
        customer_phone="+919999999999",
        current_mode="bot",
        status="active",
    )
    db_session.add(conv)
    await db_session.flush()
    await db_session.refresh(conv)

    msg = Message(
        conversation_id=conv.id,
        company_id=sample_company_id,
        sender_type="customer",
        message_text="need price for DRAGON",
    )
    db_session.add(msg)
    await db_session.flush()
    await db_session.refresh(msg)

    fake = FakeSheetsClient()
    fake.sheet_titles = {"Sheet1"}
    await GoogleSheetsSyncService(db_session, client=fake).sync_conversation(conv)

    assert fake.added_sheets == ["Leads"]
    assert any(call[1] == "Leads!A1:D1" for call in fake.updated)
    lead_call = next(call for call in fake.appended if call[1] == "Leads!A:D")
    assert lead_call[0] == "sheet123"
    assert lead_call[2][0] == [
        "+919999999999",
        "need price for DRAGON",
        "need price for DRAGON",
        "cold",
    ]
