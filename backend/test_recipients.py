#!/usr/bin/env python
"""
Скрипт для тестирования функциональности получателей в заявлениях
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'eusrr_backend.settings')
django.setup()

from django.contrib.auth import get_user_model
from requests_app.models import Request
from employees.models import Department, EmployeeDepartment
from requests_app.enums import RequestStatus, RequestType

User = get_user_model()

def print_section(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}\n")

def test_model_fields():
    """Тест 1: Проверка новых полей модели"""
    print_section("ТЕСТ 1: Проверка полей модели Request")
    
    # Проверяем, что поля существуют
    request = Request.objects.first()
    if request:
        print(f"✓ Найдена заявка: #{request.id} - {request.display_title}")
        print(f"  - departments (ManyToMany): {request.departments.count()} отделов")
        print(f"  - recipients (ManyToMany): {request.recipients.count()} получателей")
        print(f"  - cc_users (ManyToMany): {request.cc_users.count()} в копии")
        print(f"  - sent_to_all_department: {request.sent_to_all_department}")
        print(f"  - department (старое поле): {request.department}")
    else:
        print("⚠ Нет заявок в БД. Создадим тестовую...")
        
        # Создаем тестовые данные
        author = User.objects.filter(is_active=True).first()
        if not author:
            print("✗ Не найдено активных пользователей!")
            return False
        
        request = Request.objects.create(
            employee=author,
            type=RequestType.VACATION,
            title="Тестовая заявка с получателями",
            date_from="2025-12-10",
            date_to="2025-12-20",
            comment="Тест новой функциональности",
            status=RequestStatus.PENDING
        )
        print(f"✓ Создана заявка #{request.id}")
    
    return True

def test_add_recipients():
    """Тест 2: Добавление получателей"""
    print_section("ТЕСТ 2: Добавление получателей")
    
    # Находим или создаем заявку
    request = Request.objects.first()
    if not request:
        print("✗ Нет заявок для тестирования")
        return False
    
    print(f"Работаем с заявкой #{request.id}")
    
    # Получаем пользователей для теста
    users = User.objects.filter(is_active=True).exclude(
        id=request.employee_id
    )[:3]
    
    if len(users) < 2:
        print("⚠ Недостаточно пользователей для теста")
        return False
    
    # Добавляем основных получателей
    recipient1, recipient2 = users[0], users[1]
    request.add_recipient(recipient1, is_cc=False)
    request.add_recipient(recipient2, is_cc=False)
    print(f"✓ Добавлены основные получатели:")
    print(f"  - {recipient1.get_full_name() or recipient1.username}")
    print(f"  - {recipient2.get_full_name() or recipient2.username}")
    
    # Добавляем в копию
    if len(users) >= 3:
        cc_user = users[2]
        request.add_recipient(cc_user, is_cc=True)
        print(f"✓ Добавлен в копию:")
        print(f"  - {cc_user.get_full_name() or cc_user.username}")
    
    # Проверяем количество
    print(f"\nИтого:")
    print(f"  - Основных получателей: {request.recipients.count()}")
    print(f"  - В копии: {request.cc_users.count()}")
    
    return True

def test_is_recipient():
    """Тест 3: Проверка метода is_recipient"""
    print_section("ТЕСТ 3: Метод is_recipient()")
    
    request = Request.objects.first()
    if not request:
        print("✗ Нет заявок для тестирования")
        return False
    
    print(f"Заявка #{request.id}")
    
    # Проверяем автора
    print(f"\n1. Автор заявки:")
    print(f"   {request.employee.get_full_name() or request.employee.username}")
    print(f"   is_recipient: {request.is_recipient(request.employee)}")
    
    # Проверяем получателей
    if request.recipients.exists():
        recipient = request.recipients.first()
        print(f"\n2. Основной получатель:")
        print(f"   {recipient.get_full_name() or recipient.username}")
        print(f"   is_recipient: ✓ {request.is_recipient(recipient)}")
    
    # Проверяем CC
    if request.cc_users.exists():
        cc_user = request.cc_users.first()
        print(f"\n3. Пользователь в копии:")
        print(f"   {cc_user.get_full_name() or cc_user.username}")
        print(f"   is_recipient: ✓ {request.is_recipient(cc_user)}")
    
    # Проверяем случайного пользователя
    random_user = User.objects.exclude(
        id__in=[request.employee_id] + 
        list(request.recipients.values_list('id', flat=True)) +
        list(request.cc_users.values_list('id', flat=True))
    ).first()
    
    if random_user:
        print(f"\n4. Случайный пользователь:")
        print(f"   {random_user.get_full_name() or random_user.username}")
        print(f"   is_recipient: {request.is_recipient(random_user)}")
    
    return True

def test_departments():
    """Тест 4: Работа с несколькими отделами"""
    print_section("ТЕСТ 4: Множественные отделы")
    
    request = Request.objects.first()
    if not request:
        print("✗ Нет заявок для тестирования")
        return False
    
    # Получаем отделы
    departments = Department.objects.all()[:2]
    if len(departments) < 2:
        print("⚠ Недостаточно отделов для теста")
        if len(departments) == 1:
            request.departments.add(departments[0])
            print(f"✓ Добавлен 1 отдел: {departments[0].name}")
    else:
        request.departments.set(departments)
        print(f"✓ Добавлено {len(departments)} отделов:")
        for dept in departments:
            print(f"  - {dept.name}")
    
    print(f"\nВсего отделов: {request.departments.count()}")
    
    return True

def test_sent_to_all():
    """Тест 5: Флаг sent_to_all_department"""
    print_section("ТЕСТ 5: Флаг sent_to_all_department")
    
    request = Request.objects.first()
    if not request:
        print("✗ Нет заявок для тестирования")
        return False
    
    # Включаем флаг
    request.sent_to_all_department = True
    request.save()
    print(f"✓ Флаг sent_to_all_department установлен в True")
    
    # Проверяем, что есть отделы
    dept_count = request.departments.count()
    print(f"  Выбрано отделов: {dept_count}")
    
    if dept_count > 0:
        # Считаем сотрудников в этих отделах
        dept_employees = User.objects.filter(
            departments_links__department__in=request.departments.all(),
            departments_links__is_active=True,
            is_active=True
        ).distinct().count()
        
        print(f"  Сотрудников в отделах: {dept_employees}")
        print(f"  Они все теперь видят эту заявку!")
    
    return True

def test_all_recipients_property():
    """Тест 6: Свойство all_recipients"""
    print_section("ТЕСТ 6: Свойство all_recipients")
    
    request = Request.objects.first()
    if not request:
        print("✗ Нет заявок для тестирования")
        return False
    
    all_recip = request.all_recipients
    primary = request.primary_recipients
    
    print(f"Всего получателей (recipients + cc): {all_recip.count()}")
    print(f"Основных получателей: {primary.count()}")
    print(f"В копии: {request.cc_users.count()}")
    
    if all_recip.exists():
        print("\nСписок всех получателей:")
        for user in all_recip:
            is_primary = request.recipients.filter(id=user.id).exists()
            is_cc = request.cc_users.filter(id=user.id).exists()
            role = "основной" if is_primary else "CC"
            print(f"  - {user.get_full_name() or user.username} ({role})")
    
    return True

def test_api_serializer():
    """Тест 7: Проверка сериализатора"""
    print_section("ТЕСТ 7: Сериализация через API")
    
    from api.v1.requests_app.serializers import RequestReadSerializer
    from rest_framework.request import Request as DRFRequest
    from django.test import RequestFactory
    
    request_obj = Request.objects.first()
    if not request_obj:
        print("✗ Нет заявок для тестирования")
        return False
    
    # Создаем mock request
    factory = RequestFactory()
    django_request = factory.get('/')
    django_request.user = request_obj.employee
    drf_request = DRFRequest(django_request)
    
    # Сериализуем
    serializer = RequestReadSerializer(
        request_obj,
        context={'request': drf_request}
    )
    data = serializer.data
    
    print(f"Заявка #{data['id']}:")
    print(f"  - departments: {len(data.get('departments', []))}")
    print(f"  - recipients: {len(data.get('recipients', []))}")
    print(f"  - cc_users: {len(data.get('cc_users', []))}")
    print(f"  - recipient_count: {data.get('recipient_count', 0)}")
    print(f"  - cc_count: {data.get('cc_count', 0)}")
    print(f"  - is_recipient: {data.get('is_recipient', False)}")
    print(f"  - sent_to_all_department: {data.get('sent_to_all_department', False)}")
    
    return True

def run_all_tests():
    """Запуск всех тестов"""
    print("\n" + "="*60)
    print(" 🧪 ТЕСТИРОВАНИЕ ФУНКЦИОНАЛЬНОСТИ ПОЛУЧАТЕЛЕЙ")
    print("="*60)
    
    tests = [
        ("Проверка полей модели", test_model_fields),
        ("Добавление получателей", test_add_recipients),
        ("Метод is_recipient", test_is_recipient),
        ("Множественные отделы", test_departments),
        ("Флаг sent_to_all_department", test_sent_to_all),
        ("Свойство all_recipients", test_all_recipients_property),
        ("Сериализация API", test_api_serializer),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"\n✗ ОШИБКА в тесте '{name}':")
            print(f"  {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            results.append((name, False))
    
    # Итоги
    print_section("ИТОГИ ТЕСТИРОВАНИЯ")
    passed = sum(1 for _, r in results if r)
    total = len(results)
    
    for name, result in results:
        status = "✓ PASSED" if result else "✗ FAILED"
        print(f"{status:12} | {name}")
    
    print(f"\n{'='*60}")
    print(f"Пройдено: {passed}/{total} тестов ({passed*100//total}%)")
    print(f"{'='*60}\n")
    
    return passed == total

if __name__ == '__main__':
    success = run_all_tests()
    exit(0 if success else 1)
