"""
URL routing для Communications REST API

Этот модуль определяет DRF router с ViewSets для:
- Chats (чаты)
- Messages (сообщения)
- Polls (голосования)

Использование в главном urls.py:
    from communications.api.urls import router as communications_router
    path('api/v1/communications/', include(communications_router.urls))

История:
- Создан: 11 марта 2026 (перенос из api/v1/)
"""
from rest_framework.routers import DefaultRouter
from .viewsets import ChatViewSet, MessageViewSet, PollViewSet

# Создаем DRF router
router = DefaultRouter()

# Регистрируем ViewSets
router.register(r'chats', ChatViewSet, basename='chats')
router.register(r'messages', MessageViewSet, basename='messages')
router.register(r'polls', PollViewSet, basename='polls')

# Экспортируем для использования в главном urls.py
urlpatterns = router.urls

__all__ = ['router', 'urlpatterns']
