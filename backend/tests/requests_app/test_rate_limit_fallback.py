import time
import pytest
from django.urls import reverse

pytestmark = pytest.mark.django_db


def test_request_create_cache_rate_limit_fixed_window(client, user, login, monkeypatch, settings):
    login(user)

    import requests_app.views as v
    monkeypatch.setattr(v, "RATE_LIMIT_AVAILABLE", False)

    url = reverse("requests_app:request_create")

    for _ in range(15):
        assert client.get(url).status_code == 200

    assert client.get(url).status_code == 429

    real_time = time.time  # сохраняем оригинал
    monkeypatch.setattr(v.time, "time", lambda: real_time() + 61)

    assert client.get(url).status_code == 200
