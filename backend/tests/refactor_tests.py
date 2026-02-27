#!/usr/bin/env python3
"""
Скрипт для автоматического рефакторинга тестов.
Заменяет дублирующиеся функции на импорты из conftest.py.
"""

import re
from pathlib import Path

# Базовая директория
BASE_DIR = Path(__file__).parent

# Файлы для обновления
FILES = [
    'api/v1/employees/test_ldap_optional_register.py',
    'api/v1/employees/test_ldap_optional_groups.py',
    'api/v1/employees/test_role_assignment.py',
    'api/v1/employees/test_employees.py',
    'api/v1/employees/test_employees_fields_in_list.py',
    'api/v1/employees/test_email_verification_security.py',
    'api/v1/employees/test_department_roles_extra.py',
    'api/v1/employees/test_department_roles.py',
    'api/v1/employees/test_department_membership_separation.py',
    'api/v1/employees/test_department_head_rights.py',
    'api/v1/employees/test_departments.py',
    'api/v1/documents/test_documents_api.py',
    'api/v1/feed/test_posts.py',
    'api/v1/calendar_app/conftest.py',
    'api/v1/requests_app/conftest.py',
]

def add_imports(content: str) -> str:
    """Добавляет импорты если их нет."""
    lines = content.split('\n')
    
    # Находим последнюю строку импортов
    last_import_idx = 0
    for i, line in enumerate(lines):
        if line.startswith('import ') or line.startswith('from '):
            last_import_idx = i
    
    # Проверяем наличие импортов
    has_unique_phone = '_unique_phone' in content and 'from tests.conftest import' in content
    has_password = 'DEFAULT_PASSWORD' in content and 'from tests.test_config import' in content
    
    imports_to_add = []
    if not has_unique_phone and '_unique_phone()' in content:
        imports_to_add.append('from tests.conftest import _unique_phone')
    if not has_password and 'password="pass"' in content:
        imports_to_add.append('from tests.test_config import DEFAULT_PASSWORD')
    
    if imports_to_add:
        # Вставляем после последнего импорта
        for imp in reversed(imports_to_add):
            lines.insert(last_import_idx + 1, imp)
    
    return '\n'.join(lines)

def remove_duplicate_functions(content: str) -> str:
    """Удаляет дублирующиеся функции."""
    
    # Удаление _unique_phone
    patterns = [
        r'_phone_seq = count\(\d+\)\s*\n\s*\n\s*def _unique_phone\(\)[^\n]*:\s*return f"\+7999\{next\(_phone_seq\):[^}]+\}"',
        r'def _unique_phone\(\)[^\n]*:\s*(?:import random\s*)?return f"\+7999000\{[^}]+\}"',
        r'_seq = \d+\s*\n\s*def _uniq_phone\(\):\s*global _seq\s*_seq \+= 1\s*return f"\+7999\{_seq:[^}]+\}"',
    ]
    
    for pattern in patterns:
        content = re.sub(pattern, '', content, flags=re.MULTILINE)
    
    # Удаление _uniq_email
    pattern = r'def _uniq_email\([^)]*\):\s*global _seq\s*_seq \+= 1\s*return f"[^"]+"'
    content = re.sub(pattern, '', content, flags=re.MULTILINE)
    
    # Очистка лишних пустых строк
    content = re.sub(r'\n\n\n+', '\n\n', content)
    
    return content

def replace_function_calls(content: str) -> str:
    """Заменяет вызовы функций."""
    replacements = [
        (r'_uniq_email\(\)', '_unique_email()'),
        (r'_uniq_phone\(\)', '_unique_phone()'),
        (r'password="pass"', 'password=DEFAULT_PASSWORD'),
    ]
    
    for old, new in replacements:
        content = content.replace(old, new)
    
    return content

def convert_make_user_to_fixture(content: str, filename: str) -> str:
    """Конвертирует функцию make_user в fixture."""
    
    # Если есть функция make_user, оборачиваем в fixture
    if 'def make_user(' in content and '@pytest.fixture' not in content.split('def make_user(')[0].split('\n')[-2]:
        # Находим определение make_user
        pattern = r'(def make_user\([^)]*\)[^\n]*:)'
        match = re.search(pattern, content)
        if match:
            # Добавляем fixture перед функцией
            old_def = match.group(0)
            new_def = f"@pytest.fixture\n{old_def}\n    \"\"\"Fixture для создания пользователей.\"\"\""
            content = content.replace(old_def, new_def, 1)
    
    return content

def process_file(file_path: Path) -> bool:
    """Обрабатывает один файл."""
    if not file_path.exists():
        print(f"  ⏭️  Файл не найден: {file_path}")
        return False
    
    try:
        content = file_path.read_text(encoding='utf-8')
        original = content
        
        # Применяем трансформации
        content = add_imports(content)
        content = remove_duplicate_functions(content)
        content = replace_function_calls(content)
        content = convert_make_user_to_fixture(content, file_path.name)
        
        if content != original:
            file_path.write_text(content, encoding='utf-8')
            print(f"  ✅ {file_path.name}")
            return True
        else:
            print(f"  ⏭️  {file_path.name} (без изменений)")
            return False
            
    except Exception as e:
        print(f"  ❌ {file_path.name}: {e}")
        return False

def main():
    print("🔄 Автоматический рефакторинг тестов\n")
    print("=" * 60)
    
    updated = 0
    for file_rel in FILES:
        file_path = BASE_DIR / file_rel
        if process_file(file_path):
            updated += 1
    
    print("=" * 60)
    print(f"\n✅ Обновлено: {updated}/{len(FILES)} файлов")
    print("\n📝 Рекомендуется проверить тесты:")
    print("  .venv/Scripts/python -m pytest backend/tests/api/v1/employees/ -v")

if __name__ == '__main__':
    main()
