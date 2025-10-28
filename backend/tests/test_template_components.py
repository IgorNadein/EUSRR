"""
Тесты для проверки синтаксиса компонентов шаблонов.
Проверяет, что компоненты не содержат тегов, принадлежащих родительским layout'ам.
"""
import os
from pathlib import Path
from django.test import TestCase
from django.template import loader, TemplateSyntaxError


class TemplateComponentsTestCase(TestCase):
    """Тесты синтаксиса компонентов шаблонов"""
    
    # Список всех компонентов для проверки
    COMPONENTS = [
        # Компоненты employees/department
        'employees/components/department_header.html',
        'employees/components/department_info.html',
        'employees/components/department_team_circle.html',
        'employees/components/department_sidebar.html',
        'employees/components/department_modals.html',
        'employees/components/department_scripts.html',
        'employees/components/department_styles.html',
        
        # Компоненты employees/employee_form
        'employees/components/employee_form_personal.html',
        'employees/components/employee_form_contact.html',
        'employees/components/employee_form_position.html',
        'employees/components/employee_form_actions.html',
        'employees/components/employee_form_scripts.html',
        'employees/_employee_edit.html',
    ]
    
    # Главные шаблоны, которые используют компоненты
    MAIN_TEMPLATES = [
        'employees/department_detail.html',
        'includes/rightbar_calendar.html',
    ]
    
    # Недопустимые теги в компонентах (они должны быть только в layout'ах)
    FORBIDDEN_TAGS = [
        '{% extends ',
        '{% block content %}',
        '{% block extra_css %}',
        '{% block extra_js %}',
    ]
    
    def test_components_syntax(self):
        """Проверка синтаксиса всех компонентов через Django template loader"""
        errors = []
        
        for template_path in self.COMPONENTS:
            try:
                loader.get_template(template_path)
            except TemplateSyntaxError as e:
                errors.append(f"{template_path}: {e}")
            except Exception as e:
                errors.append(f"{template_path}: Unexpected error - {e}")
        
        if errors:
            error_msg = "\n".join([f"  - {err}" for err in errors])
            self.fail(f"Found {len(errors)} template syntax errors:\n{error_msg}")
    
    def test_main_templates_syntax(self):
        """Проверка синтаксиса главных шаблонов"""
        errors = []
        
        for template_path in self.MAIN_TEMPLATES:
            try:
                loader.get_template(template_path)
            except TemplateSyntaxError as e:
                errors.append(f"{template_path}: {e}")
            except Exception as e:
                errors.append(f"{template_path}: Unexpected error - {e}")
        
        if errors:
            error_msg = "\n".join([f"  - {err}" for err in errors])
            self.fail(f"Found {len(errors)} main template syntax errors:\n{error_msg}")
    
    def test_components_no_forbidden_tags(self):
        """Проверка, что компоненты не содержат тегов layout'ов"""
        from django.conf import settings
        templates_dir = Path(settings.BASE_DIR) / 'templates'
        
        errors = []
        
        for template_path in self.COMPONENTS:
            file_path = templates_dir / template_path
            if not file_path.exists():
                continue
                
            content = file_path.read_text(encoding='utf-8')
            
            # Проверка на недопустимые теги
            for forbidden_tag in self.FORBIDDEN_TAGS:
                if forbidden_tag in content:
                    errors.append(f"{template_path}: contains forbidden tag '{forbidden_tag}'")
        
        if errors:
            error_msg = "\n".join([f"  - {err}" for err in errors])
            self.fail(f"Found {len(errors)} components with forbidden layout tags:\n{error_msg}")
    
    def test_components_no_orphan_endblock(self):
        """Проверка, что компоненты не содержат одиноких {% endblock %}"""
        from django.conf import settings
        templates_dir = Path(settings.BASE_DIR) / 'templates'
        
        errors = []
        
        for template_path in self.COMPONENTS:
            file_path = templates_dir / template_path
            if not file_path.exists():
                continue
                
            content = file_path.read_text(encoding='utf-8')
            
            # Проверка на {% endblock %} (должен быть только в layout'ах)
            if '{% endblock %}' in content or '{% endblock' in content:
                # Получаем номера строк с endblock
                lines_with_endblock = [
                    i + 1 for i, line in enumerate(content.splitlines())
                    if '{% endblock' in line
                ]
                errors.append(
                    f"{template_path}: contains orphan {{% endblock %}} on line(s) {lines_with_endblock}"
                )
        
        if errors:
            error_msg = "\n".join([f"  - {err}" for err in errors])
            self.fail(f"Found {len(errors)} components with orphan endblock tags:\n{error_msg}")
    
    def test_balanced_tags(self):
        """Проверка баланса открывающих/закрывающих тегов"""
        from django.conf import settings
        templates_dir = Path(settings.BASE_DIR) / 'templates'
        
        errors = []
        
        tag_pairs = [
            ('{% if ', '{% endif %}'),
            ('{% for ', '{% endfor %}'),
            ('{% with ', '{% endwith %}'),
        ]
        
        for template_path in self.COMPONENTS:
            file_path = templates_dir / template_path
            if not file_path.exists():
                continue
                
            content = file_path.read_text(encoding='utf-8')
            
            for open_tag, close_tag in tag_pairs:
                open_count = content.count(open_tag)
                close_count = content.count(close_tag)
                
                if open_count != close_count:
                    errors.append(
                        f"{template_path}: unbalanced tags - "
                        f"{open_count} × '{open_tag}' but {close_count} × '{close_tag}'"
                    )
        
        if errors:
            error_msg = "\n".join([f"  - {err}" for err in errors])
            self.fail(f"Found {len(errors)} components with unbalanced tags:\n{error_msg}")
