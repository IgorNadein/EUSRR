# backend\requests_app\constants.py
from django.conf import settings


MAX_ATTACHMENT_SIZE = 10 * 1024 * 1024  # 10 MB
SAFE_EXTENSIONS = ["pdf", "jpg", "jpeg", "png"]
_ALLOWED_EXTS_DOTTED = {
    e if str(e).startswith(".") else f".{e}"
    for e in SAFE_EXTENSIONS
}
SAFE_MIME_TYPES = {"application/pdf", "image/png", "image/jpeg"}
PAGINATE_MY = getattr(settings, "REQUESTS_PAGINATE_BY_MY", 15)
PAGINATE_ALL = getattr(settings, "REQUESTS_PAGINATE_BY_ALL", 25)
MAX_COMMENT_LEN = getattr(settings, "REQUESTS_MAX_COMMENT_LEN", 4000)
ALLOWED_SORTS_ALL = {"-created_at", "created_at", "-decided_at", "decided_at"}
