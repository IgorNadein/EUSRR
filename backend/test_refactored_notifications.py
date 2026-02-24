"""
Тест рефакторенных уведомлений
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'eusrr_backend.settings')
django.setup()

try:
    # Импорты задач
    from notifications.tasks import (
        process_message_notifications_task,
        process_event_notifications_task,
        process_post_notifications_task,
        process_request_notifications_task,
        process_document_notifications_task,
    )
    
    # Импорты процессоров
    from notifications.task_base import (
        BaseNotificationProcessor,
        MessageNotificationProcessor,
        EventNotificationProcessor,
        PostNotificationProcessor,
        RequestNotificationProcessor,
        DocumentNotificationProcessor,
        truncate_text,
    )
    
    print("✅ Все импорты успешны!")
    print(f"✅ process_message_notifications_task: {process_message_notifications_task}")
    print(f"✅ process_event_notifications_task: {process_event_notifications_task}")
    print(f"✅ process_post_notifications_task: {process_post_notifications_task}")
    print(f"✅ process_request_notifications_task: {process_request_notifications_task}")
    print(f"✅ process_document_notifications_task: {process_document_notifications_task}")
    print(f"✅ BaseNotificationProcessor: {BaseNotificationProcessor}")
    print(f"✅ MessageNotificationProcessor: {MessageNotificationProcessor}")
    print(f"✅ EventNotificationProcessor: {EventNotificationProcessor}")
    print(f"✅ PostNotificationProcessor: {PostNotificationProcessor}")
    print(f"✅ RequestNotificationProcessor: {RequestNotificationProcessor}")
    print(f"✅ DocumentNotificationProcessor: {DocumentNotificationProcessor}")
    print(f"✅ truncate_text: {truncate_text}")
    
    # Тест функции truncate_text
    assert truncate_text("Short text", 100) == "Short text"
    assert truncate_text("Very long text that should be truncated", 10) == "Very long..."
    print("✅ truncate_text работает корректно")
    
    print("\n🎉 Рефакторинг завершён успешно!")
    
except Exception as e:
    print(f"❌ Ошибка: {e}")
    import traceback
    traceback.print_exc()
