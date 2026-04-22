"""Client for the external LogStorm attendance analyzer API."""

from dataclasses import dataclass
from datetime import date
from typing import Any, Optional

import requests
from django.conf import settings


class LogStormClientError(RuntimeError):
    """Raised when LogStorm cannot process an attendance request."""

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


@dataclass(frozen=True)
class LogStormConfig:
    base_url: str
    token: str = ""
    timeout: int = 30


def load_logstorm_config() -> LogStormConfig:
    return LogStormConfig(
        base_url=getattr(
            settings, "LOGSTORM_API_URL", "http://127.0.0.1:8000"
        ).rstrip("/"),
        token=getattr(settings, "LOGSTORM_API_TOKEN", ""),
        timeout=getattr(settings, "LOGSTORM_TIMEOUT_SECONDS", 30),
    )


class LogStormClient:
    """Small synchronous client for EUSRR -> LogStorm calls."""

    def __init__(
        self,
        config: Optional[LogStormConfig] = None,
        session: Optional[requests.Session] = None,
    ):
        self.config = config or load_logstorm_config()
        self.session = session or requests.Session()

    def analyze_attendance(self, payload: dict[str, Any]) -> dict[str, Any]:
        response = self.session.post(
            self._url("/attendance/analyze"),
            json=payload,
            headers=self._headers(),
            timeout=self.config.timeout,
        )
        if not response.ok:
            raise LogStormClientError(
                f"LogStorm API returned HTTP {response.status_code}: "
                f"{response.text}",
                status_code=response.status_code,
            )
        try:
            return response.json()
        except ValueError as exc:
            raise LogStormClientError("LogStorm API returned invalid JSON") from exc

    def update_attendance_override(
        self,
        *,
        employee_id: str,
        record_date: date | str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        response = self.session.patch(
            self._url(f"/attendance/overrides/{employee_id}/{record_date}"),
            json=payload,
            headers=self._headers(),
            timeout=self.config.timeout,
        )
        if not response.ok:
            raise LogStormClientError(
                f"LogStorm API returned HTTP {response.status_code}: "
                f"{response.text}",
                status_code=response.status_code,
            )
        try:
            return response.json()
        except ValueError as exc:
            raise LogStormClientError("LogStorm API returned invalid JSON") from exc

    def get_attendance_day_events(
        self,
        *,
        employee_id: str,
        record_date: date | str,
    ) -> list[dict[str, Any]]:
        response = self.session.get(
            self._url("/attendance/events/day/"),
            params={
                "employee_id": str(employee_id),
                "date": str(record_date),
            },
            headers=self._headers(),
            timeout=self.config.timeout,
        )
        if not response.ok:
            raise LogStormClientError(
                f"LogStorm API returned HTTP {response.status_code}: "
                f"{response.text}",
                status_code=response.status_code,
            )
        try:
            payload = response.json()
        except ValueError as exc:
            raise LogStormClientError("LogStorm API returned invalid JSON") from exc
        if not isinstance(payload, list):
            raise LogStormClientError("LogStorm API returned invalid events payload")
        return payload

    def get_attendance_event_photo(self, event_key: str) -> requests.Response:
        headers = self._headers()
        headers["Accept"] = "image/*"
        response = self.session.get(
            self._url(f"/attendance/events/photos/{event_key}/"),
            headers=headers,
            timeout=self.config.timeout,
        )
        if not response.ok:
            raise LogStormClientError(
                f"LogStorm API returned HTTP {response.status_code}: "
                f"{response.text}",
                status_code=response.status_code,
            )
        return response

    def health(self) -> bool:
        try:
            response = self.session.get(
                self._url("/health"),
                headers=self._headers(),
                timeout=self.config.timeout,
            )
        except requests.RequestException:
            return False
        return response.ok

    def _url(self, path: str) -> str:
        return f"{self.config.base_url}/{path.lstrip('/')}"

    def _headers(self) -> dict[str, str]:
        headers = {"Accept": "application/json"}
        if self.config.token:
            headers["Authorization"] = f"Bearer {self.config.token}"
        return headers
