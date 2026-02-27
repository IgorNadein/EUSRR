"""
Инструмент для анализа запросов к БД в Django views.

Использование:
    python backend/scripts/analyze_queries.py

Этот скрипт запускает тестовые запросы к API endpoints
и подсчитывает количество SQL запросов для каждого.
"""

import os
import sys
import django
from collections import defaultdict
from contextlib import contextmanager

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'eusrr_backend.settings')
django.setup()

from django.db import connection, reset_queries
from django.test import RequestFactory
from django.contrib.auth.models import AnonymousUser

# Import views after Django setup
from api.v1.employees.views import (
    EmployeeViewSet,
    EmployeeActionViewSet,
    DepartmentViewSet,
    DepartmentRoleViewSet,
    GroupViewSet,
    SkillViewSet,
    PositionViewSet,
)
from employees.models import Employee, Department, Skill, Position, Group


@contextmanager
def count_queries(label=""):
    """Контекстный менеджер для подсчета запросов."""
    reset_queries()
    yield
    num_queries = len(connection.queries)
    
    print(f"\n{'='*70}")
    print(f"📊 {label}")
    print(f"{'='*70}")
    print(f"Запросов к БД: {num_queries}")
    
    if num_queries > 0:
        print(f"\nВремя выполнения:")
        total_time = sum(float(q['time']) for q in connection.queries)
        print(f"  Общее: {total_time:.4f}s")
        print(f"  Среднее: {total_time/num_queries:.4f}s")
        
        print(f"\nСамые медленные запросы:")
        sorted_queries = sorted(connection.queries, key=lambda x: float(x['time']), reverse=True)
        for i, query in enumerate(sorted_queries[:3], 1):
            sql = query['sql'][:100] + "..." if len(query['sql']) > 100 else query['sql']
            print(f"  {i}. {query['time']}s: {sql}")
        
        print(f"\nВсе запросы:")
        for i, query in enumerate(connection.queries, 1):
            sql = query['sql'].replace('\n', ' ').replace('  ', ' ')
            if len(sql) > 150:
                sql = sql[:150] + "..."
            print(f"  {i:2d}. {query['time']}s: {sql}")
    
    return num_queries


def create_test_user():
    """Создать тестового пользователя."""
    user, created = Employee.objects.get_or_create(
        email='testuser@example.com',
        defaults={
            'first_name': 'Test',
            'last_name': 'User',
            'is_active': True,
            'is_staff': True,
        }
    )
    return user


def analyze_employee_viewset():
    """Анализ EmployeeViewSet."""
    factory = RequestFactory()
    user = create_test_user()
    
    # Test list
    with count_queries("GET /api/v1/employees/ (list)"):
        request = factory.get('/api/v1/employees/')
        request.user = user
        view = EmployeeViewSet.as_view({'get': 'list'})
        response = view(request)
    
    # Test retrieve
    with count_queries(f"GET /api/v1/employees/{user.id}/ (retrieve)"):
        request = factory.get(f'/api/v1/employees/{user.id}/')
        request.user = user
        view = EmployeeViewSet.as_view({'get': 'retrieve'})
        response = view(request, pk=user.id)
    
    # Test me
    with count_queries("GET /api/v1/employees/me/ (own profile)"):
        request = factory.get('/api/v1/employees/me/')
        request.user = user
        view = EmployeeViewSet.as_view({'get': 'me'})
        response = view(request)
    
    # Test export_excel
    with count_queries("GET /api/v1/employees/export-excel/ (export)"):
        request = factory.get('/api/v1/employees/export-excel/')
        request.user = user
        view = EmployeeViewSet.as_view({'get': 'export_excel'})
        response = view(request)


def analyze_department_viewset():
    """Анализ DepartmentViewSet."""
    factory = RequestFactory()
    user = create_test_user()
    
    with count_queries("GET /api/v1/departments/ (list)"):
        request = factory.get('/api/v1/departments/')
        request.user = user
        view = DepartmentViewSet.as_view({'get': 'list'})
        response = view(request)
    
    # Если есть отделы, тестируем retrieve
    if Department.objects.exists():
        dept = Department.objects.first()
        with count_queries(f"GET /api/v1/departments/{dept.id}/ (retrieve)"):
            request = factory.get(f'/api/v1/departments/{dept.id}/')
            request.user = user
            view = DepartmentViewSet.as_view({'get': 'retrieve'})
            response = view(request, pk=dept.id)


def analyze_skill_viewset():
    """Анализ SkillViewSet."""
    factory = RequestFactory()
    user = create_test_user()
    
    with count_queries("GET /api/v1/skills/ (list)"):
        request = factory.get('/api/v1/skills/')
        request.user = user
        view = SkillViewSet.as_view({'get': 'list'})
        response = view(request)


def analyze_group_viewset():
    """Анализ GroupViewSet."""
    factory = RequestFactory()
    user = create_test_user()
    
    with count_queries("GET /api/v1/groups/ (list)"):
        request = factory.get('/api/v1/groups/')
        request.user = user
        view = GroupViewSet.as_view({'get': 'list'})
        response = view(request)
    
    # Если есть группы, тестируем retrieve
    if Group.objects.exists():
        group = Group.objects.first()
        with count_queries(f"GET /api/v1/groups/{group.id}/ (retrieve)"):
            request = factory.get(f'/api/v1/groups/{group.id}/')
            request.user = user
            view = GroupViewSet.as_view({'get': 'retrieve'})
            response = view(request, pk=group.id)


def analyze_position_viewset():
    """Анализ PositionViewSet."""
    factory = RequestFactory()
    user = create_test_user()
    
    with count_queries("GET /api/v1/positions/ (list)"):
        request = factory.get('/api/v1/positions/')
        request.user = user
        view = PositionViewSet.as_view({'get': 'list'})
        response = view(request)


def print_summary(results):
    """Вывод сводки результатов."""
    print("\n" + "="*70)
    print("📈 СВОДКА РЕЗУЛЬТАТОВ")
    print("="*70)
    
    for endpoint, count in results.items():
        status = "✅" if count <= 5 else "⚠️" if count <= 10 else "🔴"
        print(f"{status} {endpoint:50s} {count:3d} queries")
    
    print("\n" + "="*70)
    print("Легенда:")
    print("  ✅ Отлично (1-5 запросов)")
    print("  ⚠️  Приемлемо (6-10 запросов)")
    print("  🔴 Требует оптимизации (>10 запросов)")
    print("="*70)


def main():
    """Главная функция."""
    print("\n" + "🔍 АНАЛИЗ ЗАПРОСОВ К БД В EMPLOYEES VIEWS ".center(70, "="))
    print("="*70)
    
    results = {}
    
    # Включаем отладку запросов
    from django.conf import settings
    settings.DEBUG = True
    
    try:
        print("\n🔹 Анализ EmployeeViewSet...")
        analyze_employee_viewset()
        
        print("\n🔹 Анализ DepartmentViewSet...")
        analyze_department_viewset()
        
        print("\n🔹 Анализ SkillViewSet...")
        analyze_skill_viewset()
        
        print("\n🔹 Анализ GroupViewSet...")
        analyze_group_viewset()
        
        print("\n🔹 Анализ PositionViewSet...")
        analyze_position_viewset()
        
    except Exception as e:
        print(f"\n❌ Ошибка при анализе: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "="*70)
    print("✨ Анализ завершен!")
    print("="*70)
    
    print("\n💡 Рекомендации:")
    print("  1. Используйте Django Debug Toolbar для детального анализа")
    print("  2. Добавьте select_related() для ForeignKey связей")
    print("  3. Добавьте prefetch_related() для ManyToMany связей")
    print("  4. Используйте Prefetch() для кастомизации prefetch запросов")
    print("  5. Применяйте annotate() и Subquery() вместо отдельных запросов")
    print("\n📚 Смотрите backend/docs/reports/DB_QUERIES_ANALYSIS.md")


if __name__ == '__main__':
    main()
