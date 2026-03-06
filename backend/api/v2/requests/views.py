"""Requests API v2 Views."""
from api.v1.requests_app.views import RequestViewSet as V1RequestViewSet


class RequestViewSet(V1RequestViewSet):
    """
    API v2 для заявок.

    Наследуется от v1, использует ту же логику.
    """
    pass
