"""Minimal Google Sheets API client using service-account credentials."""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Optional
from urllib.parse import quote

import httpx
import jwt

from app.core.config import settings

_TOKEN_URL = "https://oauth2.googleapis.com/token"
_SHEETS_BASE = "https://sheets.googleapis.com/v4/spreadsheets"
_SCOPE = "https://www.googleapis.com/auth/spreadsheets"


class GoogleSheetsNotConfigured(RuntimeError):
    """Raised when service-account credentials are missing."""


class GoogleSheetsClient:
    def __init__(self) -> None:
        self._token: Optional[str] = None
        self._token_expiry = 0.0

    @property
    def is_configured(self) -> bool:
        service_account = bool(
            settings.google_service_account_json or settings.google_service_account_file
        )
        oauth = bool(
            (settings.google_oauth_client_json or settings.google_oauth_client_file)
            and settings.google_oauth_refresh_token
        )
        return service_account or oauth

    def _load_service_account(self) -> dict[str, Any]:
        raw = settings.google_service_account_json
        if not raw and settings.google_service_account_file:
            raw = Path(settings.google_service_account_file).read_text(encoding="utf-8")
        if not raw:
            raise GoogleSheetsNotConfigured("Google service-account credentials are not configured.")
        info = json.loads(raw)
        if isinstance(info.get("private_key"), str):
            info["private_key"] = info["private_key"].replace("\\n", "\n")
        return info

    def _load_oauth_client(self) -> dict[str, Any]:
        raw = settings.google_oauth_client_json
        if not raw and settings.google_oauth_client_file:
            raw = Path(settings.google_oauth_client_file).read_text(encoding="utf-8")
        if not raw:
            raise GoogleSheetsNotConfigured("Google OAuth client credentials are not configured.")
        data = json.loads(raw)
        if isinstance(data, dict) and isinstance(data.get("web"), dict):
            return data["web"]
        if isinstance(data, dict) and isinstance(data.get("installed"), dict):
            return data["installed"]
        return data

    async def _access_token(self) -> str:
        now = time.time()
        if self._token and now < self._token_expiry - 60:
            return self._token

        if settings.google_oauth_refresh_token and (
            settings.google_oauth_client_json or settings.google_oauth_client_file
        ):
            return await self._oauth_access_token(now)

        info = self._load_service_account()
        issued = int(now)
        assertion = jwt.encode(
            {
                "iss": info["client_email"],
                "scope": _SCOPE,
                "aud": _TOKEN_URL,
                "iat": issued,
                "exp": issued + 3600,
            },
            info["private_key"],
            algorithm="RS256",
        )
        async with httpx.AsyncClient(timeout=settings.google_sheets_timeout_seconds) as client:
            res = await client.post(
                _TOKEN_URL,
                data={
                    "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                    "assertion": assertion,
                },
            )
            res.raise_for_status()
            data = res.json()
        self._token = str(data["access_token"])
        self._token_expiry = now + int(data.get("expires_in", 3600))
        return self._token

    async def _oauth_access_token(self, now: float) -> str:
        client_info = self._load_oauth_client()
        refresh_token = settings.google_oauth_refresh_token
        if not refresh_token:
            raise GoogleSheetsNotConfigured("GOOGLE_OAUTH_REFRESH_TOKEN is not configured.")

        async with httpx.AsyncClient(timeout=settings.google_sheets_timeout_seconds) as client:
            res = await client.post(
                _TOKEN_URL,
                data={
                    "grant_type": "refresh_token",
                    "client_id": client_info["client_id"],
                    "client_secret": client_info["client_secret"],
                    "refresh_token": refresh_token,
                },
            )
            res.raise_for_status()
            data = res.json()
        self._token = str(data["access_token"])
        self._token_expiry = now + int(data.get("expires_in", 3600))
        return self._token

    async def _request(
        self,
        method: str,
        url: str,
        *,
        json_body: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        token = await self._access_token()
        async with httpx.AsyncClient(timeout=settings.google_sheets_timeout_seconds) as client:
            res = await client.request(
                method,
                url,
                headers={"Authorization": f"Bearer {token}"},
                json=json_body,
            )
            res.raise_for_status()
            if not res.content:
                return {}
            return res.json()

    async def create_spreadsheet(self, title: str) -> tuple[str, str]:
        data = await self._request(
            "POST",
            _SHEETS_BASE,
            json_body={
                "properties": {"title": title},
                "sheets": [
                    {"properties": {"title": "Leads"}},
                ],
            },
        )
        spreadsheet_id = str(data["spreadsheetId"])
        return spreadsheet_id, str(data.get("spreadsheetUrl") or self.spreadsheet_url(spreadsheet_id))

    async def update_values(
        self,
        spreadsheet_id: str,
        range_name: str,
        values: list[list[Any]],
    ) -> None:
        encoded = quote(range_name, safe="")
        await self._request(
            "PUT",
            f"{_SHEETS_BASE}/{spreadsheet_id}/values/{encoded}?valueInputOption=RAW",
            json_body={"values": values},
        )

    async def append_values(
        self,
        spreadsheet_id: str,
        range_name: str,
        values: list[list[Any]],
    ) -> None:
        encoded = quote(range_name, safe="")
        await self._request(
            "POST",
            f"{_SHEETS_BASE}/{spreadsheet_id}/values/{encoded}:append"
            "?valueInputOption=RAW&insertDataOption=INSERT_ROWS",
            json_body={"values": values},
        )

    async def get_values(self, spreadsheet_id: str, range_name: str) -> list[list[Any]]:
        encoded = quote(range_name, safe="")
        data = await self._request("GET", f"{_SHEETS_BASE}/{spreadsheet_id}/values/{encoded}")
        values = data.get("values", [])
        return values if isinstance(values, list) else []

    async def get_sheet_titles(self, spreadsheet_id: str) -> set[str]:
        data = await self._request("GET", f"{_SHEETS_BASE}/{spreadsheet_id}?fields=sheets.properties.title")
        sheets = data.get("sheets", [])
        titles: set[str] = set()
        if isinstance(sheets, list):
            for sheet in sheets:
                props = sheet.get("properties") if isinstance(sheet, dict) else None
                title = props.get("title") if isinstance(props, dict) else None
                if isinstance(title, str):
                    titles.add(title)
        return titles

    async def add_sheet(self, spreadsheet_id: str, title: str) -> None:
        await self._request(
            "POST",
            f"{_SHEETS_BASE}/{spreadsheet_id}:batchUpdate",
            json_body={"requests": [{"addSheet": {"properties": {"title": title}}}]},
        )

    @staticmethod
    def spreadsheet_url(spreadsheet_id: str) -> str:
        return f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/edit"
