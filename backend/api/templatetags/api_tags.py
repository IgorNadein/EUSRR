# backend/api/templatetags/api_tags.py
import json
from django import template
from api.client import SESSION_KEY_ACCESS  # 'api.jwt_access'

register = template.Library()


@register.simple_tag
def api_access_token(request):
    """
    Возвращает access-токен из сессии (если есть) для использования на фронте.
    Безопасность: это тот же токен, которым ты и так ходишь на API.
    """
    try:
        return request.session.get(SESSION_KEY_ACCESS, "") or ""
    except Exception:
        return ""


@register.filter
def jsonify(obj):
    """
    Конвертирует Python объект в JSON строку
    """
    return json.dumps(obj)
