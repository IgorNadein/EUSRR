#!/usr/bin/env python
"""
Скрипт для обновления тестов - заменяет локальные helper функции на импорты из test_helpers.
"""
import re
import sys
from pathlib import Path

# Файлы для обработки
test_dir = Path("tests/api/v1/employees")

files_to_update = [
    "test_department_head_rights.py",
    "test_department_membership_separation.py",
    "test_department_roles.py",
    "test_department_roles_extra.py",
    "test_departments.py",
    "test_email_verification_security.py",
    "test_employee_actions.py",
    "test_employees.py",
    "test_employees_fields_in_list.py",
    "test_ldap_optional_groups.py",
    "test_positions.py",
    "test_role_assignment.py",
    "test_skills.py",
]


def add_import_if_missing(content: str) -> str:
    """Добавляет импорт test_helpers если его нет."""
    import_line = "from tests.api.v1.employees.test_helpers import make_user, grant_permission, make_department, extract_results"

    if "test_helpers" in content:
        return content

    # Находим последний import
    import_pattern = r'^(import |from )'
    lines = content.split('\n')
    last_import_idx = 0

    for i, line in enumerate(lines):
        if re.match(import_pattern, line):
            last_import_idx = i

    # Вставляем после последнего импорта
    lines.insert(last_import_idx + 1, import_line)

    return '\n'.join(lines)


def remove_local_functions(content: str) -> str:
    """Удаляет локальные определения helper функций."""

    # Паттерны для удаления
    patterns = [
        # make_user fixture
        r'@pytest\.fixture\s+def make_user\([^)]*\)[^:]*:.*?(?=\n(?:def |class |@pytest|$))',
        # make_user обычная функция
        r'def make_user\([^)]*\)[^:]*:.*?(?=\n(?:def |class |@pytest|$))',
        # _make_user
        r'def _make_user\([^)]*\)[^:]*:.*?(?=\n(?:def |class |@pytest|$))',
        # _user
        r'def _user\([^)]*\)[^:]*:.*?(?=\n(?:def |class |@pytest|$))',
        # _grant, _grant_perm
        r'def _grant(?:_perm)?\([^)]*\)[^:]*:.*?(?=\n(?:def |class |@pytest|$))',
        # _unique_phone, _unique_email
        r'def _unique_(?:phone|email)\([^)]*\)[^:]*:.*?(?=\n(?:def |class |@pytest|$))',
        # extract_results
        r'def extract_results\([^)]*\)[^:]*:.*?(?=\n(?:def |class |@pytest|$))',
    ]

    for pattern in patterns:
        content = re.sub(pattern, '', content, flags=re.DOTALL | re.MULTILINE)

    return content


def replace_function_calls(content: str) -> str:
    """Заменяет вызовы локальных функций на импортированные."""
    replacements = {
        r'\b_make_user\(': 'make_user(',
        r'\b_user\(': 'make_user(',
        r'\b_grant\(': 'grant_permission(',
        r'\b_grant_perm\(': 'grant_permission(',
    }

    for old, new in replacements.items():
        content = re.sub(old, new, content)

    return content


def update_file(filepath: Path):
    """Обновляет один файл."""
    print(f"Обновляем {filepath.name}...")

    content = filepath.read_text(encoding='utf-8')

    # Добавляем импорт
    content = add_import_if_missing(content)

    # Удаляем локальные функции
    content = remove_local_functions(content)

    # Заменяем вызовы
    content = replace_function_calls(content)

    # Убираем лишние пустые строки
    content = re.sub(r'\n{3,}', '\n\n', content)

    filepath.write_text(content, encoding='utf-8')
    print(f"  ✓ {filepath.name} обновлен")


def main():
    """Главная функция."""
    for filename in files_to_update:
        filepath = test_dir / filename
        if filepath.exists():
            try:
                update_file(filepath)
            except Exception as e:
                print(f"  ✗ Ошибка в {filename}: {e}", file=sys.stderr)
        else:
            print(f"  ! {filename} не найден")

    print("\n✅ Обновление завершено!")


if __name__ == "__main__":
    main()
