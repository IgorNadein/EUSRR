"""Documents API v2 Views."""
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from api.v1.documents.views import DocumentViewSet as V1DocumentViewSet


class DocumentViewSet(V1DocumentViewSet):
    """
    API v2 для документов.

    Наследуется от v1, но может быть расширен в будущем.
    """
    pass
