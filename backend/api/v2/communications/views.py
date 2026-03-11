"""Communications API v2 Views."""
from communications.api.viewsets import (
    ChatViewSet as V1ChatViewSet,
    MessageViewSet as V1MessageViewSet,
    PollViewSet as V1PollViewSet,
)


class ChatViewSet(V1ChatViewSet):
    """API v2 для чатов."""
    pass


class MessageViewSet(V1MessageViewSet):
    """API v2 для сообщений."""
    pass


class PollViewSet(V1PollViewSet):
    """API v2 для опросов."""
    pass
