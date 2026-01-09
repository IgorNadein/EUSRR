"""
Тесты для проверки результатов рефакторинга модуля notifications.
"""
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'eusrr_backend.settings')
django.setup()

print('Тестирование рефакторинга notifications...')
print()

passed = 0
failed = 0

# Тест 1: Импорт процессоров
try:
    from notifications.task_base import (
        BaseNotificationProcessor,
        MessageNotificationProcessor,
        EventNotificationProcessor,
        PostNotificationProcessor,
        RequestNotificationProcessor,
        DocumentNotificationProcessor,
        truncate_text
    )
    print('[PASS] Task processors imported')
    passed += 1
except Exception as e:
    print(f'[FAIL] Task processors import failed: {e}')
    failed += 1

# Тест 2: Импорт задач
try:
    from notifications.tasks import (
        process_message_notifications_task,
        process_event_notifications_task,
        process_post_notifications_task,
        process_request_notifications_task,
        process_document_notifications_task
    )
    print('[PASS] Celery tasks imported')
    passed += 1
except Exception as e:
    print(f'[FAIL] Celery tasks import failed: {e}')
    failed += 1

# Тест 3: Импорт новых API views
try:
    from api.v1.notifications.views import (
        get_notifications,
        mark_as_read,
        get_user_settings,
        subscribe_push,
        get_telegram_link_status
    )
    print('[PASS] API v1 views imported (16 endpoints)')
    passed += 1
except Exception as e:
    print(f'[FAIL] API v1 views import failed: {e}')
    failed += 1

# Тест 4: Проверка truncate_text
try:
    from notifications.task_base import truncate_text
    result = truncate_text('Test message that is very long', 10)
    assert result == 'Test messa...', f'Expected "Test messa...", got "{result}"'
    
    result2 = truncate_text('Short', 100)
    assert result2 == 'Short', f'Expected "Short", got "{result2}"'
    
    result3 = truncate_text('', 10)
    assert result3 == '', f'Expected empty string, got "{result3}"'
    
    print('[PASS] truncate_text works correctly')
    passed += 1
except Exception as e:
    print(f'[FAIL] truncate_text failed: {e}')
    failed += 1

# Тест 5: Проверка, что задачи зарегистрированы в Celery
try:
    from notifications.tasks import process_message_notifications_task
    assert hasattr(process_message_notifications_task, 'delay'), 'Task should have delay method'
    assert hasattr(process_message_notifications_task, 'apply_async'), 'Task should have apply_async method'
    assert process_message_notifications_task.name == 'communications.process_message_notifications'
    print('[PASS] Celery tasks are properly registered')
    passed += 1
except Exception as e:
    print(f'[FAIL] Celery task registration failed: {e}')
    failed += 1

# Тест 6: Проверка URL роутинга
try:
    from django.urls import reverse, resolve
    
    # Проверяем новые URL
    url = reverse('api:v1:notifications_api_v1:list')
    assert url == '/api/v1/notifications/', f'Expected /api/v1/notifications/, got {url}'
    
    url2 = reverse('api:v1:notifications_api_v1:count')
    assert url2 == '/api/v1/notifications/count/', f'Expected /api/v1/notifications/count/, got {url2}'
    
    print('[PASS] URL routing configured correctly')
    passed += 1
except Exception as e:
    print(f'[FAIL] URL routing failed: {e}')
    failed += 1

# Тест 7: Проверка сигналов
try:
    import communications.notification_signals
    import calendar_app.notification_signals
    import feed.notification_signals
    import requests_app.notification_signals
    import documents.notification_signals
    print('[PASS] Notification signals imported')
    passed += 1
except Exception as e:
    print(f'[FAIL] Notification signals import failed: {e}')
    failed += 1

# Тест 8: Проверка старых deprecated файлов
try:
    from notifications import api_views, api_urls
    import warnings
    # Проверяем, что файлы содержат deprecation warning
    with open('notifications/api_views.py', 'r', encoding='utf-8') as f:
        content = f.read()
        assert 'DEPRECATED' in content, 'api_views.py should have DEPRECATED notice'
    
    with open('notifications/api_urls.py', 'r', encoding='utf-8') as f:
        content = f.read()
        assert 'DEPRECATED' in content, 'api_urls.py should have DEPRECATED notice'
    
    print('[PASS] Deprecated files marked correctly')
    passed += 1
except Exception as e:
    print(f'[FAIL] Deprecated files check failed: {e}')
    failed += 1

# Тест 9: Проверка размера файлов
try:
    import os
    
    tasks_size = os.path.getsize('notifications/tasks.py')
    task_base_size = os.path.getsize('notifications/task_base.py')
    
    # tasks.py должен быть значительно меньше task_base.py после рефакторинга
    # tasks.py ~ 380 строк (20-25KB), task_base.py ~ 600 строк (25-35KB)
    assert tasks_size < 30000, f'tasks.py too large: {tasks_size} bytes (expected < 30KB)'
    assert task_base_size > 20000, f'task_base.py too small: {task_base_size} bytes (expected > 20KB)'
    
    print(f'[PASS] File sizes correct (tasks.py: {tasks_size//1024}KB, task_base.py: {task_base_size//1024}KB)')
    passed += 1
except Exception as e:
    print(f'[FAIL] File size check failed: {e}')
    failed += 1

# Тест 10: Проверка, что процессоры наследуются от базового класса
try:
    from notifications.task_base import (
        BaseNotificationProcessor,
        MessageNotificationProcessor,
        EventNotificationProcessor
    )
    
    assert issubclass(MessageNotificationProcessor, BaseNotificationProcessor)
    assert issubclass(EventNotificationProcessor, BaseNotificationProcessor)
    
    # Проверяем наличие обязательных методов
    assert hasattr(MessageNotificationProcessor, 'process')
    assert hasattr(BaseNotificationProcessor, 'send_notifications')
    assert hasattr(BaseNotificationProcessor, 'log_result')
    
    print('[PASS] Processor inheritance structure correct')
    passed += 1
except Exception as e:
    print(f'[FAIL] Processor inheritance check failed: {e}')
    failed += 1

print()
print('=' * 50)
print(f'Результаты: {passed} PASSED, {failed} FAILED')
print('=' * 50)

if failed == 0:
    print('Все тесты пройдены успешно!')
    sys.exit(0)
else:
    print(f'Обнаружены ошибки в {failed} тестах')
    sys.exit(1)
