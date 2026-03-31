"""Кастомные классы пагинации для API."""

from rest_framework.pagination import PageNumberPagination


class StandardPagination(PageNumberPagination):
    """Стандартная пагинация с поддержкой параметра page_size.

    Позволяет клиенту указывать размер страницы через параметр page_size,
    с ограничением максимального размера страницы.
    """
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 10000  # Максимальный размер страницы
