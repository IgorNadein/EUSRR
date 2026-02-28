# backend/search/search_indexes.py
"""
Регистрация моделей для полнотекстового поиска через django-watson.

Этот файл автоматически загружается при запуске Django если следовать
стандартной структуре watson.
"""
from __future__ import annotations

from watson.search import register
from django.apps import apps


def get_model_safe(app_label: str, model_name: str):
    """Безопасное получение модели (если приложение установлено)."""
    try:
        return apps.get_model(app_label, model_name)
    except LookupError:
        return None


# ==================== РЕГИСТРАЦИЯ МОДЕЛЕЙ ====================

# 1. Посты (Feed)
Post = get_model_safe("feed", "Post")
if Post:
    register(
        Post,
        fields=("title", "body"),
        store=("title", "created_at"),
    )

# 2. Сотрудники (Employees)
Employee = get_model_safe("employees", "Employee")
if Employee:
    register(
        Employee,
        fields=(
            "last_name",
            "first_name", 
            "patronymic",
            "email",
            "phone_number",
        ),
        store=("last_name", "first_name", "patronymic", "email"),
    )

# 3. Отделы (Departments)
Department = get_model_safe("employees", "Department")
if Department:
    register(
        Department,
        fields=("name", "description"),
        store=("name", "description"),
    )

# 4. Заявления (Requests)
Request = get_model_safe("requests_app", "Request")
if Request:
    register(
        Request,
        fields=("title", "comment"),
        store=("title", "status", "created_at"),
    )

# 5. Чаты (Communications)
Chat = get_model_safe("communications", "Chat")
if Chat:
    register(
        Chat,
        fields=("name", "description"),
        store=("name",),
    )

# 6. Сообщения чатов (Communications)
Message = get_model_safe("communications", "Message")
if Message:
    register(
        Message,
        fields=("content",),
        store=("content", "created_at"),
    )

# 7. Календарные события (Calendar App)
CalendarEvent = get_model_safe("calendar_app", "CalendarEvent")
if CalendarEvent:
    from watson.search import SearchAdapter
    
    class CalendarEventAdapter(SearchAdapter):
        """Кастомный адаптер для CalendarEvent с правильным URL."""
        
        def get_url(self, obj):
            """Возвращает URL календаря (общий календарь компании)."""
            return "/calendar/"
    
    register(
        CalendarEvent,
        adapter_cls=CalendarEventAdapter,
        fields=("title", "description"),
        store=("title", "start_date"),
    )

# 8. События расписания (Django-Scheduler)
Event = get_model_safe("schedule", "Event")
if Event:
    from watson.search import SearchAdapter
    
    class ScheduleEventAdapter(SearchAdapter):
        """Кастомный адаптер для Event из django-scheduler."""
        
        def get_url(self, obj):
            """Возвращает URL календаря."""
            return "/calendar/"
    
    register(
        Event,
        adapter_cls=ScheduleEventAdapter,
        fields=("title", "description"),
        store=("title", "start"),
    )

# 9. Заявки на закупку (Procurement)
ProcurementRequest = get_model_safe("procurement", "ProcurementRequest")
if ProcurementRequest:
    register(
        ProcurementRequest,
        fields=("title", "description"),
        store=("title", "status", "created_at"),
    )

# 10. Оборудование (Procurement)
Equipment = get_model_safe("procurement", "Equipment")
if Equipment:
    register(
        Equipment,
        fields=("name", "inventory_number", "serial_number", "location"),
        store=("name", "inventory_number", "status"),
    )

# 11. Документы (Documents)
Document = get_model_safe("documents", "Document")
if Document:
    from watson.search import SearchAdapter
    
    class DocumentAdapter(SearchAdapter):
        """Кастомный адаптер для Document с URL и расширенным поиском."""
        
        def get_title(self, obj):
            """Возвращает заголовок для результатов поиска."""
            return obj.title
        
        def get_description(self, obj):
            """Возвращает описание для результатов поиска."""
            # Возвращаем первые 200 символов extracted_text или description
            text = obj.extracted_text if obj.extracted_text else obj.description
            return text[:200] + '...' if len(text) > 200 else text
        
        def get_url(self, obj):
            """Возвращает URL документа."""
            return f"/documents/{obj.id}/"
    
    register(
        Document,
        adapter_cls=DocumentAdapter,
        fields=("title", "description", "extracted_text"),  # Добавлен extracted_text!
        store=("title", "uploaded_at", "status"),
    )

# 12. Уведомления (Notifications)
Notification = get_model_safe("notifications", "Notification")
if Notification:
    register(
        Notification,
        fields=("title", "message", "short_message"),
        store=("title", "is_read", "created_at"),
    )
