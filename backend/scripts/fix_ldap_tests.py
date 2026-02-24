#!/usr/bin/env python
"""
Скрипт для массового добавления ensure_ldap_disabled fixture к тестам.

Добавляет параметр ensure_ldap_disabled к функциям тестов, которые:
- Создают объекты через Department.objects.create()
- Создают объекты через Position.objects.create()
- Не имеют уже ensure_ldap_disabled или ensure_ldap_enabled
"""
import re
import sys
from pathlib import Path


def fix_test_file(file_path: Path) -> tuple[bool, int]:
    """
    Исправляет один тестовый файл.
    
    Returns:
        (changed, count) - был ли изменен файл и количество исправленных функций
    """
    content = file_path.read_text(encoding='utf-8')
    original_content = content
    
    # Паттерн для поиска тестовых функций
    # Ищем def test_...(...): где нет ensure_ldap в параметрах
    pattern = r'(def test_\w+\([^)]*\)):'
    
    fixed_count = 0
    lines = content.split('\n')
    new_lines = []
    
    i = 0
    while i < len(lines):
        line = lines[i]
        
        # Проверяем, является ли это определением тестовой функции
        match = re.match(r'^def (test_\w+)\((.*)\):', line)
        
        if match:
            func_name = match.group(1)
            params = match.group(2)
            
            # Проверяем, нет ли уже ensure_ldap в параметрах
            if 'ensure_ldap' not in params:
                # Проверяем следующие 50 строк на наличие Department.objects.create или Position.objects.create
                check_lines = '\n'.join(lines[i:min(i+50, len(lines))])
                
                if ('Department.objects.create' in check_lines or 
                    'Position.objects.create' in check_lines or
                    'DepartmentRole.objects.create' in check_lines or
                    'make_department' in check_lines):
                    
                    # Добавляем ensure_ldap_disabled
                    if params.strip():
                        new_params = f"{params}, ensure_ldap_disabled"
                    else:
                        new_params = "ensure_ldap_disabled"
                    
                    new_line = line.replace(f"({params})", f"({new_params})")
                    new_lines.append(new_line)
                    fixed_count += 1
                    print(f"  ✓ Исправлена функция: {func_name}")
                else:
                    new_lines.append(line)
            else:
                new_lines.append(line)
        else:
            new_lines.append(line)
        
        i += 1
    
    new_content = '\n'.join(new_lines)
    
    if new_content != original_content:
        file_path.write_text(new_content, encoding='utf-8')
        return True, fixed_count
    
    return False, 0


def main():
    """Главная функция."""
    test_dir = Path(__file__).parent.parent / 'tests' / 'api' / 'v1' / 'employees'
    
    # Список файлов для исправления
    files_to_fix = [
        'test_department_membership_separation.py',
        'test_department_roles.py',
        'test_department_roles_extra.py',
        'test_departments.py',
        'test_employee_actions.py',
        'test_employees.py',
        'test_positions.py',
        'test_role_assignment.py',
        'test_skills.py',
    ]
    
    total_fixed = 0
    total_files = 0
    
    for filename in files_to_fix:
        file_path = test_dir / filename
        
        if not file_path.exists():
            print(f"⚠ Файл не найден: {filename}")
            continue
        
        print(f"\nОбрабатываем {filename}...")
        changed, count = fix_test_file(file_path)
        
        if changed:
            print(f"  ✅ {filename} исправлен ({count} функций)")
            total_fixed += count
            total_files += 1
        else:
            print(f"  ⊘ {filename} не требует изменений")
    
    print(f"\n{'='*60}")
    print(f"✅ Обработано файлов: {total_files}")
    print(f"✅ Исправлено функций: {total_fixed}")
    print(f"{'='*60}\n")


if __name__ == '__main__':
    main()
