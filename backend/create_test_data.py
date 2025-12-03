#!/usr/bin/env python
"""
Создание тестовых пользователей и отделов
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'eusrr_backend.settings')
django.setup()

from django.contrib.auth import get_user_model
from employees.models import Department, EmployeeDepartment, DepartmentRole

User = get_user_model()


def create_test_users():
    """Создание тестовых пользователей"""
    print("\n" + "="*60)
    print("  Создание тестовых пользователей")
    print("="*60)
    
    users_data = [
        {
            'username': 'recipient1',
            'email': 'recipient1@test.local',
            'first_name': 'Получатель',
            'last_name': 'Первый',
            'password': 'test123'
        },
        {
            'username': 'recipient2',
            'email': 'recipient2@test.local',
            'first_name': 'Получатель',
            'last_name': 'Второй',
            'password': 'test123'
        },
        {
            'username': 'recipient3',
            'email': 'recipient3@test.local',
            'first_name': 'Получатель',
            'last_name': 'Третий',
            'password': 'test123'
        },
        {
            'username': 'cc_user1',
            'email': 'cc_user1@test.local',
            'first_name': 'Копия',
            'last_name': 'Первый',
            'password': 'test123'
        },
        {
            'username': 'cc_user2',
            'email': 'cc_user2@test.local',
            'first_name': 'Копия',
            'last_name': 'Второй',
            'password': 'test123'
        },
    ]
    
    created_users = []
    for user_data in users_data:
        username = user_data['username']
        
        # Проверяем, существует ли
        if User.objects.filter(username=username).exists():
            user = User.objects.get(username=username)
            print(f"  ⚠ Пользователь {username} уже существует")
        else:
            user = User.objects.create_user(**user_data)
            user.is_active = True
            user.save()
            print(f"  ✓ Создан {username} - {user.get_full_name()}")
        
        created_users.append(user)
    
    return created_users


def create_test_departments():
    """Создание тестовых отделов"""
    print("\n" + "="*60)
    print("  Создание тестовых отделов")
    print("="*60)
    
    departments_data = [
        {'name': 'Отдел тестирования 1', 'code': 'TEST_DEPT_1'},
        {'name': 'Отдел тестирования 2', 'code': 'TEST_DEPT_2'},
    ]
    
    created_depts = []
    for dept_data in departments_data:
        code = dept_data['code']
        
        if Department.objects.filter(code=code).exists():
            dept = Department.objects.get(code=code)
            print(f"  ⚠ Отдел {code} уже существует")
        else:
            dept = Department.objects.create(**dept_data)
            print(f"  ✓ Создан отдел {dept.name}")
        
        created_depts.append(dept)
    
    return created_depts


def link_users_to_departments(users, departments):
    """Привязка пользователей к отделам"""
    print("\n" + "="*60)
    print("  Привязка пользователей к отделам")
    print("="*60)
    
    if not departments:
        print("  ⚠ Нет отделов для привязки")
        return
    
    # Получаем или создаем роль
    role, created = DepartmentRole.objects.get_or_create(
        name='Сотрудник',
        defaults={'description': 'Обычный сотрудник отдела'}
    )
    
    if created:
        print(f"  ✓ Создана роль: {role.name}")
    
    # Привязываем пользователей
    for i, user in enumerate(users):
        dept = departments[i % len(departments)]
        
        link, created = EmployeeDepartment.objects.get_or_create(
            employee=user,
            department=dept,
            defaults={'role': role, 'is_active': True}
        )
        
        if created:
            print(f"  ✓ {user.username} → {dept.name}")
        else:
            print(f"  ⚠ {user.username} уже в {dept.name}")


def show_summary():
    """Показать итоги"""
    print("\n" + "="*60)
    print("  ИТОГИ")
    print("="*60)
    
    total_users = User.objects.filter(is_active=True).count()
    total_depts = Department.objects.count()
    total_links = EmployeeDepartment.objects.filter(is_active=True).count()
    
    print(f"\nАктивных пользователей: {total_users}")
    print(f"Отделов: {total_depts}")
    print(f"Связей пользователь-отдел: {total_links}")
    
    print("\nПользователи для тестирования:")
    test_users = User.objects.filter(
        username__in=['recipient1', 'recipient2', 'recipient3', 'cc_user1', 'cc_user2']
    )
    for user in test_users:
        depts = user.departments_links.filter(is_active=True)
        dept_names = ', '.join([d.department.name for d in depts])
        print(f"  - {user.username}: {user.get_full_name()} ({dept_names})")


if __name__ == '__main__':
    print("\n" + "="*60)
    print(" 🔧 ПОДГОТОВКА ТЕСТОВЫХ ДАННЫХ")
    print("="*60)
    
    users = create_test_users()
    departments = create_test_departments()
    link_users_to_departments(users, departments)
    show_summary()
    
    print("\n✓ Готово! Теперь можно запускать тесты API.\n")
