import pytest

from django.urls import reverse
from rest_framework.test import APIClient


pytestmark = pytest.mark.django_db


@pytest.fixture
def api_client() -> APIClient:
    return APIClient()


def test_openapi_schema_is_available(api_client: APIClient):
    response = api_client.get(
        reverse("api:schema"),
        HTTP_ACCEPT="application/json",
    )

    assert response.status_code == 200

    payload = response.json()
    assert payload["openapi"].startswith("3.")
    assert "/api/auth/token/" in payload["paths"]
    assert "/api/auth/register/" in payload["paths"]
    assert "/api/auth/sessions/" in payload["paths"]
    assert "/api/v1/auth/token/" in payload["paths"]
    assert "/api/v1/auth/register/" in payload["paths"]
    assert "/api/v1/auth/sessions/" in payload["paths"]
    assert "/api/v1/documents/" in payload["paths"]
    assert "/api/v1/notifications/" in payload["paths"]
    assert "/api/v1/procurement/stats/overview/" in payload["paths"]
    assert "/api/v1/requests/" in payload["paths"]
    assert "/api/v1/search/" in payload["paths"]
    assert "/api/procurement/requests/" not in payload["paths"]

    tag_names = {tag["name"] for tag in payload.get("tags", [])}
    assert {
        "Auth",
        "Documents",
        "Notifications",
        "Procurement",
        "Requests",
        "Search",
    }.issubset(tag_names)


def test_swagger_and_redoc_pages_are_available(api_client: APIClient):
    swagger_response = api_client.get(reverse("api:swagger-ui"))
    redoc_response = api_client.get(reverse("api:redoc"))

    assert swagger_response.status_code == 200
    assert redoc_response.status_code == 200

    assert "swagger-ui" in swagger_response.content.decode().lower()
    assert "redoc" in redoc_response.content.decode().lower()


def test_websocket_asyncapi_schema_is_available(api_client: APIClient):
    response = api_client.get(reverse("api:ws-schema"))

    assert response.status_code == 200
    assert "application/yaml" in response["Content-Type"]

    schema = response.content.decode()
    assert "asyncapi: 2.6.0" in schema
    assert "address: /ws/" in schema
    assert "OpenChatAction" in schema
    assert "NotificationEvent" in schema


def test_websocket_asyncapi_docs_page_is_available(api_client: APIClient):
    response = api_client.get(reverse("api:ws-docs"))

    assert response.status_code == 200

    html = response.content.decode().lower()
    assert "websocket asyncapi" in html
    assert reverse("api:ws-schema") in response.content.decode()
    assert "/ws/" in response.content.decode()
