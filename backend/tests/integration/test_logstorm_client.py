import pytest

from common.logstorm_client import (
    LogStormClient,
    LogStormClientError,
    LogStormConfig,
    load_logstorm_config,
)


class FakeResponse:
    def __init__(self, status_code=200, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload
        self.text = text
        self.ok = 200 <= status_code < 400

    def json(self):
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload


class FakeSession:
    def __init__(self, response):
        self.response = response
        self.requests = []

    def post(self, url, **kwargs):
        self.requests.append(("POST", url, kwargs))
        return self.response

    def get(self, url, **kwargs):
        self.requests.append(("GET", url, kwargs))
        return self.response


def _payload():
    return {
        "employee_id": "100",
        "period_start": "2026-04-20",
        "period_end": "2026-04-20",
        "schedule": {
            "start_time": "09:00",
            "end_time": "18:00",
            "expected_hours": 9,
            "workdays": ["Monday"],
            "date_overrides": [],
        },
    }


def test_load_logstorm_config_reads_settings(settings):
    settings.LOGSTORM_API_URL = "http://logstorm:8000/"
    settings.LOGSTORM_API_TOKEN = "secret"
    settings.LOGSTORM_TIMEOUT_SECONDS = 12

    config = load_logstorm_config()

    assert config.base_url == "http://logstorm:8000"
    assert config.token == "secret"
    assert config.timeout == 12


def test_analyze_attendance_posts_payload_with_bearer_token():
    session = FakeSession(FakeResponse(payload={"records": []}))
    client = LogStormClient(
        LogStormConfig(
            base_url="http://logstorm:8000",
            token="secret",
            timeout=7,
        ),
        session=session,
    )

    result = client.analyze_attendance(_payload())

    assert result == {"records": []}
    method, url, kwargs = session.requests[0]
    assert method == "POST"
    assert url == "http://logstorm:8000/attendance/analyze"
    assert kwargs["json"]["employee_id"] == "100"
    assert kwargs["headers"]["Authorization"] == "Bearer secret"
    assert kwargs["timeout"] == 7


def test_analyze_attendance_raises_on_http_error():
    client = LogStormClient(
        LogStormConfig(base_url="http://logstorm:8000"),
        session=FakeSession(FakeResponse(status_code=500, text="boom")),
    )

    with pytest.raises(LogStormClientError, match="HTTP 500"):
        client.analyze_attendance(_payload())


def test_analyze_attendance_raises_on_invalid_json():
    client = LogStormClient(
        LogStormConfig(base_url="http://logstorm:8000"),
        session=FakeSession(FakeResponse(payload=ValueError("bad json"))),
    )

    with pytest.raises(LogStormClientError, match="invalid JSON"):
        client.analyze_attendance(_payload())


def test_health_returns_boolean():
    ok_client = LogStormClient(
        LogStormConfig(base_url="http://logstorm:8000"),
        session=FakeSession(FakeResponse(status_code=200, payload={})),
    )
    bad_client = LogStormClient(
        LogStormConfig(base_url="http://logstorm:8000"),
        session=FakeSession(FakeResponse(status_code=503, payload={})),
    )

    assert ok_client.health() is True
    assert bad_client.health() is False
