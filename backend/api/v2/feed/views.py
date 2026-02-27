"""Feed API v2 Views."""
from api.v1.feed.views import (
    CommentViewSet as V1CommentViewSet,
    PostViewSet as V1PostViewSet,
)


class PostViewSet(V1PostViewSet):
    """API v2 для постов."""
    pass


class CommentViewSet(V1CommentViewSet):
    """API v2 для комментариев."""
    pass
