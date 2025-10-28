#!/usr/bin/env python
"""
Быстрая проверка синтаксиса шаблонов без запуска тестов.
Использование: python check_templates.py
"""
import os
import sys
from pathlib import Path

# Настройка Django окружения
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'eusrr_backend.settings')

import django
django.setup()

from django.template import loader
from django.template.exceptions import TemplateSyntaxError
from django.conf import settings


# Цветной вывод для терминала
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    RESET = '\033[0m'
    BOLD = '\033[1m'


def check_template_syntax(template_path):
    """Проверка синтаксиса одного шаблона"""
    try:
        loader.get_template(template_path)
        return True, None
    except TemplateSyntaxError as e:
        return False, str(e)
    except Exception as e:
        return False, f"Unexpected error: {e}"


def check_forbidden_tags(template_path):
    """Проверка на недопустимые теги в компонентах"""
    templates_dir = Path(settings.BASE_DIR) / 'templates'
    file_path = templates_dir / template_path
    
    if not file_path.exists():
        return []
    
    forbidden_tags = [
        '{% extends ',
        '{% block content %}',
        '{% block extra_css %}',
        '{% block extra_js %}',
    ]
    
    content = file_path.read_text(encoding='utf-8')
    found_tags = []
    
    for tag in forbidden_tags:
        if tag in content:
            found_tags.append(tag.strip())
    
    return found_tags


def check_orphan_endblock(template_path):
    """Проверка на одинокие {% endblock %}"""
    templates_dir = Path(settings.BASE_DIR) / 'templates'
    file_path = templates_dir / template_path
    
    if not file_path.exists():
        return []
    
    content = file_path.read_text(encoding='utf-8')
    lines_with_endblock = [
        i + 1 for i, line in enumerate(content.splitlines())
        if '{% endblock' in line
    ]
    
    return lines_with_endblock


def main():
    """Основная функция проверки"""
    
    # Список всех рефакторенных компонентов
    components = [
        # Department components
        'employees/components/department_header.html',
        'employees/components/department_info.html',
        'employees/components/department_team_circle.html',
        'employees/components/department_sidebar.html',
        'employees/components/department_modals.html',
        'employees/components/department_scripts.html',
        'employees/components/department_styles.html',
        
        # Employee form components
        'employees/components/employee_form_personal.html',
        'employees/components/employee_form_contact.html',
        'employees/components/employee_form_position.html',
        'employees/components/employee_form_actions.html',
        'employees/components/employee_form_scripts.html',
        'employees/_employee_edit.html',
    ]
    
    # Main templates
    main_templates = [
        'employees/department_detail.html',
        'includes/rightbar_calendar.html',
    ]
    
    print(f"\n{Colors.BOLD}=== Проверка компонентов шаблонов ==={Colors.RESET}\n")
    
    total_errors = 0
    
    # Проверка компонентов
    print(f"{Colors.BLUE}Компоненты:{Colors.RESET}")
    for template in components:
        # Проверка синтаксиса
        is_valid, error = check_template_syntax(template)
        
        if is_valid:
            print(f"  {Colors.GREEN}✓{Colors.RESET} {template}")
            
            # Дополнительные проверки для валидных шаблонов
            forbidden = check_forbidden_tags(template)
            if forbidden:
                print(f"    {Colors.YELLOW}⚠ Содержит теги layout: "
                      f"{', '.join(forbidden)}{Colors.RESET}")
                total_errors += 1
            
            endblocks = check_orphan_endblock(template)
            if endblocks:
                print(f"    {Colors.YELLOW}⚠ Содержит {{% endblock %}} "
                      f"на строках: {endblocks}{Colors.RESET}")
                total_errors += 1
        else:
            print(f"  {Colors.RED}✗{Colors.RESET} {template}")
            print(f"    {Colors.RED}Ошибка: {error}{Colors.RESET}")
            total_errors += 1
    
    # Проверка главных шаблонов
    print(f"\n{Colors.BLUE}Главные шаблоны:{Colors.RESET}")
    for template in main_templates:
        is_valid, error = check_template_syntax(template)
        
        if is_valid:
            print(f"  {Colors.GREEN}✓{Colors.RESET} {template}")
        else:
            print(f"  {Colors.RED}✗{Colors.RESET} {template}")
            print(f"    {Colors.RED}Ошибка: {error}{Colors.RESET}")
            total_errors += 1
    
    # Итоги
    print(f"\n{Colors.BOLD}=== Итоги ==={Colors.RESET}")
    print(f"Проверено шаблонов: {len(components) + len(main_templates)}")
    
    if total_errors == 0:
        print(f"{Colors.GREEN}{Colors.BOLD}✓ Все шаблоны корректны!"
              f"{Colors.RESET}")
        sys.exit(0)
    else:
        print(f"{Colors.RED}{Colors.BOLD}✗ Обнаружено ошибок: "
              f"{total_errors}{Colors.RESET}")
        sys.exit(1)


if __name__ == '__main__':
    main()
