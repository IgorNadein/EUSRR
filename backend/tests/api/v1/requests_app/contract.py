from __future__ import annotations

from typing import Any, Dict, Final


# =================== НАСТРОЙКИ КОНТРАКТА (заполни под свой проект) ===================

# Маршруты ресурса "заявления"
LIST_URL: Final[str] = "/api/v1/requests/"            # коллекция
DETAIL_URL_FMT: Final[str] = "/api/v1/requests/{id}/" # детальная карточка

# Модельное право, позволяющее видеть чужие записи (app_label.codename)
# Пример: "requests_app.view_request"
MODEL_VIEW_PERMISSION: Final[str] = "requests_app.view_request"

# Поддерживает ли API метод PUT (полная замена)
SUPPORTS_PUT: Final[bool] = True

# Политика удаления:
#   True  — "жёсткое" удаление (ожидаем 204/200 и последующий 404/410)
#   False — soft-delete/запрет (тест подстроится)
ALLOW_HARD_DELETE: Final[bool] = True

# Примеры валидных данных (ОБЯЗАТЕЛЬНО заполни по сериализатору)
SAMPLE_CREATE_PAYLOAD: Dict[str, Any] = {
    # "title": "Командировка",
    # "body": "По проекту А",
    # "start_date": "2025-09-20",
}
SAMPLE_UPDATE_PAYLOAD: Dict[str, Any] = {
    # "title": "Командировка (уточнение)"
}
SAMPLE_PUT_PAYLOAD: Dict[str, Any] = {
    # Полный набор полей для PUT (если SUPPORTS_PUT=True)
}

# =================== ВСПОМОГАТЕЛЬНОЕ ===================

def detail_url(pk: int) -> str:
    """Собирает URL детальной карточки по первичному ключу.

    Args:
        pk (int): Идентификатор записи.

    Returns:
        str: Абсолютный путь к ресурсу детальной записи.

    Raises:
        ValueError: Если DETAIL_URL_FMT не содержит плейсхолдер {id}.
    """
    if "{id}" not in DETAIL_URL_FMT:
        raise ValueError("DETAIL_URL_FMT должен содержать плейсхолдер '{id}'")
    return DETAIL_URL_FMT.format(id=pk)
