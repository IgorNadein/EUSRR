"""
Детальное тестирование API логики доступа к заявлениям
Проверяет edge cases и специфические сценарии
"""

import os
import sys
import django

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'eusrr_backend.settings')
django.setup()

from django.contrib.auth import get_user_model
from django.db import models
from employees.models import Department, EmployeeDepartment
from requests_app.models import Request
from requests_app.enums import RequestStatus

User = get_user_model()


def test_scenario(title, test_func):
    """Обертка для тестов"""
    print(f"\n{'=' * 80}")
    print(f"🧪 ТЕСТ: {title}")
    print('=' * 80)
    try:
        result = test_func()
        if result:
            print(f"✅ PASSED")
        else:
            print(f"❌ FAILED")
        return result
    except Exception as e:
        print(f"💥 ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_recipient_can_see():
    """Тест: Получатель (To) видит заявку"""
    print("\n1. Создаем пользователя и заявку...")
    
    # Находим пользователя
    user1 = User.objects.filter(is_staff=False, is_superuser=False).first()
    user2 = User.objects.filter(is_staff=False, is_superuser=False).exclude(id=user1.id).first()
    
    if not user1 or not user2:
        print("⚠️  Недостаточно пользователей для теста")
        return None
    
    print(f"   Автор: {user1.get_full_name() or user1.username}")
    print(f"   Получатель: {user2.get_full_name() or user2.username}")
    
    # Создаем заявку
    request = Request.objects.create(
        employee=user1,
        type='other',
        title='Тест: получатель должен видеть',
        status=RequestStatus.PENDING
    )
    request.recipients.add(user2)
    
    print(f"   Создана заявка ID={request.id}")
    
    # Проверяем доступ
    print("\n2. Проверяем доступ получателя...")
    from django.db.models import Q
    
    my_depts = EmployeeDepartment.objects.filter(
        employee=user2, is_active=True
    ).values_list('department_id', flat=True)
    
    scope = Q(employee_id=user2.id) | Q(recipients=user2) | Q(cc_users=user2)
    if my_depts:
        scope |= Q(sent_to_all_department=True, departments__in=my_depts)
    
    accessible = Request.objects.filter(scope).filter(id=request.id).exists()
    
    print(f"   Получатель видит заявку: {accessible}")
    
    # Cleanup
    request.delete()
    
    return accessible


def test_cc_user_can_see():
    """Тест: Пользователь в CC видит заявку"""
    print("\n1. Создаем пользователей и заявку с CC...")
    
    user1 = User.objects.filter(is_staff=False, is_superuser=False).first()
    user2 = User.objects.filter(is_staff=False, is_superuser=False).exclude(id=user1.id).first()
    
    if not user1 or not user2:
        print("⚠️  Недостаточно пользователей для теста")
        return None
    
    print(f"   Автор: {user1.get_full_name() or user1.username}")
    print(f"   CC: {user2.get_full_name() or user2.username}")
    
    request = Request.objects.create(
        employee=user1,
        type='other',
        title='Тест: CC должен видеть',
        status=RequestStatus.PENDING
    )
    request.cc_users.add(user2)
    
    print(f"   Создана заявка ID={request.id}")
    
    # Проверяем доступ
    print("\n2. Проверяем доступ CC пользователя...")
    from django.db.models import Q
    
    scope = Q(employee_id=user2.id) | Q(recipients=user2) | Q(cc_users=user2)
    accessible = Request.objects.filter(scope).filter(id=request.id).exists()
    
    print(f"   CC пользователь видит заявку: {accessible}")
    
    # Cleanup
    request.delete()
    
    return accessible


def test_all_department_visibility():
    """Тест: sent_to_all_department работает"""
    print("\n1. Создаем заявку 'Всем в отделе'...")
    
    # Находим отдел с сотрудниками
    dept = Department.objects.annotate(
        emp_count=models.Count('employeedepartment')
    ).filter(emp_count__gte=2).first()
    
    if not dept:
        print("⚠️  Нет отдела с несколькими сотрудниками")
        return None
    
    # Берем двух сотрудников этого отдела
    emp_dept = EmployeeDepartment.objects.filter(
        department=dept,
        is_active=True
    ).select_related('employee')[:2]
    
    if len(emp_dept) < 2:
        print("⚠️  Недостаточно сотрудников в отделе")
        return None
    
    author = emp_dept[0].employee
    viewer = emp_dept[1].employee
    
    print(f"   Отдел: {dept.name}")
    print(f"   Автор: {author.get_full_name() or author.username}")
    print(f"   Сотрудник отдела: {viewer.get_full_name() or viewer.username}")
    
    # Создаем заявку
    request = Request.objects.create(
        employee=author,
        type='other',
        title='Тест: Всем в отделе',
        status=RequestStatus.PENDING,
        sent_to_all_department=True
    )
    request.departments.add(dept)
    
    print(f"   Создана заявка ID={request.id}")
    
    # Проверяем доступ
    print("\n2. Проверяем, что другой сотрудник отдела видит заявку...")
    from django.db.models import Q
    
    my_depts = [dept.id]
    scope = Q(employee_id=viewer.id) | Q(recipients=viewer) | Q(cc_users=viewer)
    scope |= Q(sent_to_all_department=True, departments__in=my_depts)
    
    accessible = Request.objects.filter(scope).filter(id=request.id).exists()
    
    print(f"   Сотрудник видит заявку: {accessible}")
    
    # Cleanup
    request.delete()
    
    return accessible


def test_non_recipient_cannot_see():
    """Тест: Посторонний НЕ видит заявку"""
    print("\n1. Создаем заявку без получателей...")
    
    users = list(User.objects.filter(is_staff=False, is_superuser=False)[:3])
    if len(users) < 3:
        print("⚠️  Недостаточно пользователей")
        return None
    
    author = users[0]
    recipient = users[1]
    outsider = users[2]
    
    print(f"   Автор: {author.get_full_name() or author.username}")
    print(f"   Получатель: {recipient.get_full_name() or recipient.username}")
    print(f"   Посторонний: {outsider.get_full_name() or outsider.username}")
    
    request = Request.objects.create(
        employee=author,
        type='other',
        title='Тест: Посторонний не должен видеть',
        status=RequestStatus.PENDING
    )
    request.recipients.add(recipient)
    
    print(f"   Создана заявка ID={request.id}")
    
    # Проверяем, что посторонний НЕ видит
    print("\n2. Проверяем, что посторонний НЕ видит заявку...")
    from django.db.models import Q
    
    my_depts = EmployeeDepartment.objects.filter(
        employee=outsider, is_active=True
    ).values_list('department_id', flat=True)
    
    scope = Q(employee_id=outsider.id) | Q(recipients=outsider) | Q(cc_users=outsider)
    if my_depts:
        scope |= Q(sent_to_all_department=True, departments__in=my_depts)
    
    accessible = Request.objects.filter(scope).filter(id=request.id).exists()
    
    print(f"   Посторонний видит заявку: {accessible}")
    print(f"   Ожидается: False")
    
    # Cleanup
    request.delete()
    
    return not accessible  # Тест проходит, если НЕ видит


def main():
    print("\n" + "=" * 80)
    print("  ДЕТАЛЬНОЕ ТЕСТИРОВАНИЕ API ЛОГИКИ ДОСТУПА")
    print("=" * 80)
    
    from django.db import models
    
    results = []
    
    # Тесты
    results.append(test_scenario(
        "Получатель (To) видит заявку",
        test_recipient_can_see
    ))
    
    results.append(test_scenario(
        "Пользователь в CC видит заявку",
        test_cc_user_can_see
    ))
    
    results.append(test_scenario(
        "sent_to_all_department работает",
        test_all_department_visibility
    ))
    
    results.append(test_scenario(
        "Посторонний НЕ видит чужую заявку",
        test_non_recipient_cannot_see
    ))
    
    # Итоги
    print("\n" + "=" * 80)
    print("  ИТОГИ ТЕСТИРОВАНИЯ")
    print("=" * 80)
    
    passed = sum(1 for r in results if r is True)
    failed = sum(1 for r in results if r is False)
    skipped = sum(1 for r in results if r is None)
    
    print(f"\n✅ Пройдено: {passed}")
    print(f"❌ Провалено: {failed}")
    print(f"⏭️  Пропущено: {skipped}")
    
    if failed == 0 and passed > 0:
        print("\n🎉 Все тесты пройдены успешно!")
    elif failed > 0:
        print("\n⚠️  Есть проваленные тесты - требуется исправление!")


if __name__ == "__main__":
    main()
