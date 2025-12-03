#!/usr/bin/env python
"""
Тестирование API получателей заявлений
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'eusrr_backend.settings')
django.setup()

import json
from django.contrib.auth import get_user_model
from django.test import RequestFactory
from rest_framework.test import force_authenticate
from api.v1.requests_app.views import RequestViewSet
from api.v1.requests_app.serializers import RequestWriteSerializer
from requests_app.models import Request
from employees.models import Department

User = get_user_model()


def test_create_request_with_recipients():
    """Тест создания заявки с получателями через API"""
    print("\n" + "="*60)
    print("  ТЕСТ: Создание заявки с получателями")
    print("="*60)
    
    # Получаем пользователей
    author = User.objects.filter(is_active=True).first()
    users = User.objects.filter(is_active=True).exclude(id=author.id)[:3]
    dept = Department.objects.first()
    
    if not author or len(users) < 2 or not dept:
        print("✗ Недостаточно данных для теста")
        return False
    
    recipient1, recipient2 = users[0], users[1]
    cc_user = users[2] if len(users) > 2 else None
    
    # Данные для создания
    data = {
        'type': 'VACATION',
        'title': 'Отпуск с API тестом получателей',
        'date_from': '2025-12-10',
        'date_to': '2025-12-20',
        'comment': 'Тест API',
        'department_ids': [dept.id],
        'recipient_ids': [recipient1.id, recipient2.id],
        'sent_to_all_department': False
    }
    
    if cc_user:
        data['cc_user_ids'] = [cc_user.id]
    
    print(f"\nДанные запроса:")
    print(f"  - author: {author.get_full_name() or author.username}")
    print(f"  - recipients: {recipient1.get_full_name()}, {recipient2.get_full_name()}")
    if cc_user:
        print(f"  - cc: {cc_user.get_full_name()}")
    print(f"  - department: {dept.name}")
    
    # Создаем mock request
    factory = RequestFactory()
    request = factory.post('/api/v1/requests/', data, format='json')
    force_authenticate(request, user=author)
    
    # Сериализация
    serializer = RequestWriteSerializer(
        data=data,
        context={'request': request}
    )
    
    if not serializer.is_valid():
        print(f"\n✗ Ошибки валидации: {serializer.errors}")
        return False
    
    # Создание объекта
    request_obj = serializer.save(employee=author)
    
    print(f"\n✓ Заявка создана: #{request_obj.id}")
    print(f"  - recipients: {request_obj.recipients.count()}")
    print(f"  - cc_users: {request_obj.cc_users.count()}")
    print(f"  - departments: {request_obj.departments.count()}")
    
    # Проверяем правильность
    assert request_obj.recipients.count() == 2
    assert request_obj.is_recipient(recipient1)
    assert request_obj.is_recipient(recipient2)
    
    if cc_user:
        assert request_obj.cc_users.count() == 1
        assert request_obj.is_recipient(cc_user)
    
    print("\n✓ Все проверки прошли успешно!")
    return True


def test_queryset_addressed_to_me():
    """Тест фильтрации ?addressed_to_me=true"""
    print("\n" + "="*60)
    print("  ТЕСТ: Фильтр ?addressed_to_me=true")
    print("="*60)
    
    # Находим заявку с получателями
    request_obj = Request.objects.filter(
        recipients__isnull=False
    ).distinct().first()
    
    if not request_obj:
        print("⚠ Нет заявок с получателями")
        return False
    
    recipient = request_obj.recipients.first()
    if not recipient:
        print("⚠ Нет получателей")
        return False
    
    print(f"\nЗаявка: #{request_obj.id}")
    print(f"Получатель: {recipient.get_full_name() or recipient.username}")
    
    # Mock request
    factory = RequestFactory()
    django_request = factory.get('/api/v1/requests/?addressed_to_me=true')
    force_authenticate(django_request, user=recipient)
    
    # ViewSet
    viewset = RequestViewSet()
    viewset.request = django_request
    viewset.action = 'list'
    viewset.format_kwarg = None
    
    # Получаем queryset
    qs = viewset.get_queryset()
    
    print(f"\nКоличество заявок для пользователя: {qs.count()}")
    
    # Проверяем, что наша заявка в выборке
    if qs.filter(id=request_obj.id).exists():
        print("✓ Заявка найдена в выборке для получателя")
        return True
    else:
        print("✗ Заявка НЕ найдена в выборке")
        return False


def test_update_recipients():
    """Тест обновления получателей"""
    print("\n" + "="*60)
    print("  ТЕСТ: Обновление получателей")
    print("="*60)
    
    request_obj = Request.objects.first()
    if not request_obj:
        print("✗ Нет заявок")
        return False
    
    users = User.objects.filter(is_active=True).exclude(
        id=request_obj.employee_id
    )[:4]
    
    if len(users) < 3:
        print("⚠ Недостаточно пользователей")
        return False
    
    print(f"\nЗаявка: #{request_obj.id}")
    print(f"Было получателей: {request_obj.recipients.count()}")
    print(f"Было CC: {request_obj.cc_users.count()}")
    
    # Новые данные
    new_recipients = [users[0].id, users[1].id, users[2].id]
    new_cc = [users[3].id] if len(users) > 3 else []
    
    data = {
        'recipient_ids': new_recipients,
        'cc_user_ids': new_cc,
    }
    
    # Mock request
    factory = RequestFactory()
    django_request = factory.patch(
        f'/api/v1/requests/{request_obj.id}/',
        data,
        format='json'
    )
    force_authenticate(django_request, user=request_obj.employee)
    
    # Сериализация
    serializer = RequestWriteSerializer(
        request_obj,
        data=data,
        partial=True,
        context={'request': django_request}
    )
    
    if not serializer.is_valid():
        print(f"\n✗ Ошибки: {serializer.errors}")
        return False
    
    updated_obj = serializer.save()
    
    print(f"\n✓ Обновлено:")
    print(f"  - recipients: {updated_obj.recipients.count()}")
    print(f"  - cc_users: {updated_obj.cc_users.count()}")
    
    assert updated_obj.recipients.count() == 3
    if new_cc:
        assert updated_obj.cc_users.count() == 1
    
    print("✓ Все проверки прошли!")
    return True


if __name__ == '__main__':
    print("\n" + "="*60)
    print(" 🧪 ТЕСТИРОВАНИЕ API ПОЛУЧАТЕЛЕЙ")
    print("="*60)
    
    tests = [
        ("Создание с получателями", test_create_request_with_recipients),
        ("Фильтр addressed_to_me", test_queryset_addressed_to_me),
        ("Обновление получателей", test_update_recipients),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"\n✗ ОШИБКА: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            results.append((name, False))
    
    # Итоги
    print("\n" + "="*60)
    print("  ИТОГИ")
    print("="*60)
    
    for name, result in results:
        status = "✓ PASSED" if result else "✗ FAILED"
        print(f"{status:12} | {name}")
    
    passed = sum(1 for _, r in results if r)
    total = len(results)
    print(f"\nПройдено: {passed}/{total}")
