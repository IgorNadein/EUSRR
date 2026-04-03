from pathlib import Path

from django.conf import settings
from django.http import Http404, HttpResponse
from django.urls import reverse
from django.views.generic import TemplateView, View


ASYNCAPI_SCHEMA_PATH = (
    Path(settings.BASE_DIR)
    / "docs"
    / "architecture"
    / "websocket-asyncapi.yaml"
)


def _load_asyncapi_schema_text() -> str:
    try:
        return ASYNCAPI_SCHEMA_PATH.read_text(encoding="utf-8")
    except OSError as exc:
        raise Http404("AsyncAPI schema file not found") from exc


class AsyncAPISchemaView(View):
    """Отдаёт AsyncAPI схему WebSocket-контура отдельным endpoint."""

    http_method_names = ["get"]

    def get(self, request, *args, **kwargs):
        schema_text = _load_asyncapi_schema_text()
        response = HttpResponse(
            schema_text,
            content_type="application/yaml; charset=utf-8",
        )
        response["Content-Disposition"] = (
            'inline; filename="websocket-asyncapi.yaml"'
        )
        return response


class AsyncAPIDocsView(TemplateView):
    """Простая HTML-страница с WS-документацией и raw AsyncAPI схемой."""

    template_name = "api/websocket_docs.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        ws_scheme = "wss" if self.request.is_secure() else "ws"
        context.update(
            {
                "asyncapi_schema_url": reverse("api:ws-schema"),
                "openapi_schema_url": reverse("api:schema"),
                "swagger_url": reverse("api:swagger-ui"),
                "redoc_url": reverse("api:redoc"),
                "ws_endpoint_url": (
                    f"{ws_scheme}://{self.request.get_host()}/ws/"
                ),
                "schema_text": _load_asyncapi_schema_text(),
            }
        )
        return context
