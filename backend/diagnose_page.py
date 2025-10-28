#!/usr/bin/env python
"""
Диагностика проблем с рендерингом страниц.
Проверяет, правильно ли подключаются компоненты.
"""
import os
import sys
from pathlib import Path

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'eusrr_backend.settings')

import django
django.setup()

from django.test import RequestFactory
from django.contrib.auth import get_user_model
from django.template import loader
from employees.models import Department

User = get_user_model()


def diagnose_department_page():
    """Диагностика страницы отдела"""
    print("\n=== Диагностика страницы отдела ===\n")
    
    # Создаём mock request
    factory = RequestFactory()
    request = factory.get('/employees/departments/1/')
    
    # Пробуем получить отдел
    try:
        dept = Department.objects.first()
        if not dept:
            print("❌ Нет отделов в базе")
            return
        print(f"✓ Отдел найден: {dept.name} (ID: {dept.id})")
    except Exception as e:
        print(f"❌ Ошибка получения отдела: {e}")
        return
    
    # Пробуем загрузить шаблон
    try:
        template = loader.get_template('employees/department_detail.html')
        print("✓ Шаблон department_detail.html загружен")
    except Exception as e:
        print(f"❌ Ошибка загрузки шаблона: {e}")
        return
    
    # Проверяем компоненты
    components = [
        'employees/components/department_header.html',
        'employees/components/department_info.html',
        'employees/components/department_team_circle.html',
        'employees/components/department_sidebar.html',
        'employees/components/department_modals.html',
        'employees/components/department_styles.html',
        'employees/components/department_scripts.html',
    ]
    
    print("\nКомпоненты:")
    for comp in components:
        try:
            loader.get_template(comp)
            print(f"  ✓ {comp}")
        except Exception as e:
            print(f"  ❌ {comp}: {e}")
    
    # Проверяем календарь
    print("\nКомпоненты календаря:")
    calendar_components = [
        'includes/calendar/calendar_styles.html',
        'includes/calendar/calendar_widget.html',
        'includes/calendar/calendar_events_list.html',
        'includes/calendar/calendar_modals.html',
        'includes/calendar/calendar_scripts.html',
    ]
    
    for comp in calendar_components:
        try:
            loader.get_template(comp)
            print(f"  ✓ {comp}")
        except Exception as e:
            print(f"  ❌ {comp}: {e}")
    
    print("\n=== Проверка размеров компонентов ===\n")
    from django.conf import settings
    templates_dir = Path(settings.BASE_DIR) / 'templates'
    
    for comp in components:
        file_path = templates_dir / comp
        if file_path.exists():
            lines = len(file_path.read_text(encoding='utf-8').splitlines())
            size = file_path.stat().st_size
            print(f"  {comp}: {lines} строк, {size} байт")
        else:
            print(f"  ❌ {comp}: файл не найден")


def check_base_template():
    """Проверка base.html"""
    print("\n=== Проверка base.html ===\n")
    
    try:
        template = loader.get_template('base.html')
        print("✓ base.html загружен")
        
        # Проверяем, что в нём есть блоки
        from django.conf import settings
        base_path = Path(settings.BASE_DIR) / 'templates' / 'base.html'
        content = base_path.read_text(encoding='utf-8')
        
        checks = [
            ('{% block extra_css %}', 'Блок extra_css'),
            ('{% block extra_js %}', 'Блок extra_js'),
            ('{% include "includes/rightbar_calendar.html" %}', 'Include календаря'),
            ('bootstrap.bundle.min.js', 'Bootstrap JS'),
            ('fullcalendar', 'FullCalendar JS'),
        ]
        
        for pattern, description in checks:
            if pattern in content:
                print(f"  ✓ {description}")
            else:
                print(f"  ❌ {description} НЕ НАЙДЕН!")
                
    except Exception as e:
        print(f"❌ Ошибка: {e}")


if __name__ == '__main__':
    diagnose_department_page()
    check_base_template()
