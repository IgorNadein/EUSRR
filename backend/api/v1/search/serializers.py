# backend/api/v1/search/serializers.py
"""
Сериализаторы для API поиска через django-watson.
"""

from __future__ import annotations

from rest_framework import serializers


class SearchResultSerializer(serializers.Serializer):
    """Сериализатор для результата поиска watson."""

    model_name = serializers.CharField(
        help_text=(
            "Тип модели: post, employee, department, request, "
            "chat, message, event"
        )
    )
    object_id = serializers.IntegerField(help_text="ID объекта")
    title = serializers.CharField(
        help_text="Заголовок/имя объекта", allow_blank=True
    )
    description = serializers.CharField(
        help_text="Описание/превью контента", allow_blank=True, required=False
    )
    url = serializers.CharField(help_text="Ссылка на объект", allow_blank=True)
    meta = serializers.DictField(
        help_text="Дополнительные метаданные", required=False, allow_null=True
    )


class SearchResponseSerializer(serializers.Serializer):
    """Сериализатор для ответа API поиска."""

    query = serializers.CharField(help_text="Поисковый запрос")
    results = SearchResultSerializer(many=True)
    counts = serializers.DictField(
        help_text="Количество результатов по типам",
        child=serializers.IntegerField(),
    )
    total = serializers.IntegerField(help_text="Общее количество результатов")
