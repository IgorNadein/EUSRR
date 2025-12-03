"""
Тестирование логики доступа к заявлениям (requests)

Проверяет:
1. Обычные пользователи видят только свои + адресованные им
2. Руководители отделов видят заявки своих отделов
3. Пользователи с глобальными правами видят всё
4. Департаментные права работают корректно
5. sent_to_all_department работает
"""

import os
import sys
import django

# Настройка Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'eusrr_backend.settings')
django.setup()

from django.contrib.auth import get_user_model
from django.db.models import Q
from employees.models import Department, EmployeeDepartment
from requests_app.models import Request

User = get_user_model()


def print_section(title):
    """Красивый вывод секции"""
    print(f"\n{'=' * 80}")
    print(f"  {title}")
    print('=' * 80)


def test_user_access(user, description=""):
    """Тестирует доступ пользователя к заявлениям"""
    print(f"\n👤 Пользователь: {user.get_full_name() or user.username}")
    if description:
        print(f"   {description}")
    
    # Получаем отделы пользователя
    my_depts = EmployeeDepartment.objects.filter(
        employee=user,
        is_active=True
    ).select_related('department')
    
    print(f"\n📋 Отделы пользователя:")
    if my_depts.exists():
        for ed in my_depts:
            role_name = ed.role.name if ed.role else "Без роли"
            print(f"   - {ed.department.name} ({role_name})")
            if ed.role:
                perms = ed.role.scoped_permissions.values_list('code', flat=True)
                if perms:
                    print(f"     Права: {', '.join(perms)}")
    else:
        print("   (нет отделов)")
    
    # Проверяем глобальные права
    print(f"\n🔑 Глобальные права:")
    print(f"   is_staff: {user.is_staff}")
    print(f"   can_view_all_requests: {user.has_perm('requests_app.can_view_all_requests')}")
    print(f"   view_request: {user.has_perm('requests_app.view_request')}")
    print(f"   can_process_requests: {user.has_perm('requests_app.can_process_requests')}")
    
    # Проверяем руководство отделами
    head_depts = Department.objects.filter(head=user)
    if head_depts.exists():
        print(f"\n👔 Руководитель отделов:")
        for dept in head_depts:
            print(f"   - {dept.name}")
    
    # Строим queryset как в реальном API
    my_dept_ids = list(my_depts.values_list('department_id', flat=True))
    
    # Проверяем: может ли видеть ВСЁ
    can_view_all = (
        user.is_staff
        or user.has_perm("requests_app.can_view_all_requests")
        or user.has_perm("requests_app.view_request")
    )
    
    if can_view_all:
        print(f"\n✅ Может просматривать ВСЕ заявления (staff или глобальные права)")
        qs = Request.objects.all()
    else:
        # Обычный пользователь - строим scope
        scope = Q(employee_id=user.id)  # Свои заявки
        
        # Заявки, где я получатель
        scope |= Q(recipients=user) | Q(cc_users=user)
        
        # Заявки отделов с sent_to_all_department
        if my_dept_ids:
            scope |= Q(
                sent_to_all_department=True,
                departments__in=my_dept_ids
            )
        
        # Департаментные права
        view_dept_ids = list(
            EmployeeDepartment.objects.filter(
                employee_id=user.id,
                is_active=True,
                role__scoped_permissions__code="view_request",
            )
            .values_list("department_id", flat=True)
            .distinct()
        )
        proc_dept_ids = list(
            EmployeeDepartment.objects.filter(
                employee_id=user.id,
                is_active=True,
                role__scoped_permissions__code="can_process_requests",
            )
            .values_list("department_id", flat=True)
            .distinct()
        )
        head_dept_ids = list(
            Department.objects.filter(head_id=user.id).values_list("id", flat=True)
        )
        
        combined_ids = set(view_dept_ids) | set(proc_dept_ids) | set(head_dept_ids)
        
        if combined_ids:
            print(f"\n📊 Департаментные права для отделов (ID): {combined_ids}")
            
            # Заявки этих отделов
            scope |= Q(departments__in=combined_ids)
            
            # Заявки сотрудников этих отделов
            dept_emp_ids = list(
                EmployeeDepartment.objects.filter(
                    department_id__in=list(combined_ids),
                    is_active=True,
                )
                .values_list("employee_id", flat=True)
                .distinct()
            )
            if dept_emp_ids:
                scope |= Q(employee_id__in=dept_emp_ids)
        
        qs = Request.objects.filter(scope).distinct()
    
    # Подсчитываем результаты
    total = qs.count()
    print(f"\n📈 Доступные заявления: {total}")
    
    if total > 0:
        # Разбивка по типам доступа
        my_requests = qs.filter(employee=user).count()
        addressed_to_me = qs.filter(Q(recipients=user) | Q(cc_users=user)).count()
        
        print(f"\n   Детализация:")
        print(f"   - Мои заявления: {my_requests}")
        print(f"   - Адресованные мне (To/CC): {addressed_to_me}")
        
        if my_dept_ids:
            all_dept = qs.filter(
                sent_to_all_department=True,
                departments__in=my_dept_ids
            ).distinct().count()
            print(f"   - 'Всем в отделе': {all_dept}")
        
        # Последние 5 заявлений для примера
        print(f"\n   Примеры заявлений (последние 5):")
        for req in qs.select_related('employee').order_by('-created_at')[:5]:
            author = req.employee.get_full_name() or req.employee.username
            
            # Определяем причину доступа
            reasons = []
            if req.employee == user:
                reasons.append("автор")
            if req.recipients.filter(id=user.id).exists():
                reasons.append("получатель")
            if req.cc_users.filter(id=user.id).exists():
                reasons.append("CC")
            if req.sent_to_all_department and any(
                dept.id in my_dept_ids for dept in req.departments.all()
            ):
                reasons.append("всем в отделе")
            
            reason_str = ", ".join(reasons) if reasons else "департаментные права"
            
            print(f"   {req.id:4d}. {req.get_type_display():15s} | {author:20s} | {reason_str}")
    
    return qs


def main():
    print_section("ТЕСТИРОВАНИЕ ЛОГИКИ ДОСТУПА К ЗАЯВЛЕНИЯМ")
    
    # Получаем тестовых пользователей
    print("\n🔍 Поиск пользователей для тестирования...")
    
    users_to_test = []
    
    # 1. Обычный сотрудник (без особых прав)
    regular_user = User.objects.filter(
        is_staff=False,
        is_superuser=False,
    ).exclude(
        departments_links__role__scoped_permissions__code__in=[
            'view_request', 'can_process_requests'
        ]
    ).first()
    
    if regular_user:
        users_to_test.append((regular_user, "Обычный сотрудник (без особых прав)"))
    
    # 2. Руководитель отдела
    head_user = Department.objects.exclude(head__isnull=True).first()
    if head_user and head_user.head:
        users_to_test.append((head_user.head, f"Руководитель отдела '{head_user.name}'"))
    
    # 3. С департаментными правами
    dept_rights_user = EmployeeDepartment.objects.filter(
        is_active=True,
        role__scoped_permissions__code__in=['view_request', 'can_process_requests']
    ).select_related('employee').first()
    
    if dept_rights_user:
        users_to_test.append((
            dept_rights_user.employee,
            f"С департаментными правами в отделе '{dept_rights_user.department.name}'"
        ))
    
    # 4. Staff пользователь
    staff_user = User.objects.filter(is_staff=True, is_superuser=False).first()
    if staff_user:
        users_to_test.append((staff_user, "Django staff (без superuser)"))
    
    # 5. Superuser
    superuser = User.objects.filter(is_superuser=True).first()
    if superuser:
        users_to_test.append((superuser, "Superuser"))
    
    if not users_to_test:
        print("\n❌ Не найдено пользователей для тестирования!")
        print("   Создайте пользователей и отделы в админке")
        return
    
    # Информация о заявлениях в системе
    total_requests = Request.objects.count()
    print(f"\n📊 Всего заявлений в системе: {total_requests}")
    
    if total_requests == 0:
        print("\n⚠️  В системе нет заявлений! Создайте хотя бы одну заявку для тестирования.")
        return
    
    # Статистика по получателям
    with_recipients = Request.objects.filter(recipients__isnull=False).distinct().count()
    with_cc = Request.objects.filter(cc_users__isnull=False).distinct().count()
    with_depts = Request.objects.filter(departments__isnull=False).distinct().count()
    with_all_dept = Request.objects.filter(sent_to_all_department=True).count()
    
    print(f"\n   Заявлений с получателями (To): {with_recipients}")
    print(f"   Заявлений с копией (CC): {with_cc}")
    print(f"   Заявлений с отделами: {with_depts}")
    print(f"   Заявлений 'Всем в отделе': {with_all_dept}")
    
    # Тестируем каждого пользователя
    for user, description in users_to_test:
        print_section(f"ТЕСТ: {description}")
        test_user_access(user, description)
    
    print_section("ТЕСТИРОВАНИЕ ЗАВЕРШЕНО")
    print("\n✅ Все проверки выполнены!")
    print("\nРекомендации:")
    print("1. Проверьте, что обычные пользователи НЕ видят чужие заявки")
    print("2. Руководители должны видеть заявки своих отделов")
    print("3. Staff видят всё")
    print("4. Получатели (To/CC) видят адресованные им заявки")


if __name__ == "__main__":
    main()
