"""Documents API v2 Views."""
from api.v1.documents.views import DocumentViewSet as V1DocumentViewSet


class DocumentViewSet(V1DocumentViewSet):
    """
    API v2 для документов.

    Наследуется от v1, использует ту же логику.
    В будущем можно добавить специфичные для v2 улучшения.
    """
    pass
