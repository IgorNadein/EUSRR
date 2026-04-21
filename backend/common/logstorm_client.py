"""Client for the external LogStorm attendance analyzer API."""

from dataclasses import dataclass
from typing import Any, Optional

import requests
from django.conf import settings


class LogStormClientError(RuntimeError):
    """Raised when LogStorm cannot process an attendance request."""


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
                f"{response.text}"
            )
        try:
            return response.json()
        except ValueError as exc:
            raise LogStormClientError("LogStorm API returned invalid JSON") from exc

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
