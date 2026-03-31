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
    assert "/api/v1/auth/register/" in payload["paths"]
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
