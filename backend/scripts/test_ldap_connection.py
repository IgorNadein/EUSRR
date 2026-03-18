#!/usr/bin/env python3
"""
Тестовый скрипт для проверки подключения к LDAP серверу.

Использование:
    python scripts/test_ldap_connection.py
    
Требования:
    - Запущенный LDAP сервер через docker-compose.ldap.yml
    - Настроенные переменные окружения в .env
"""

import os
import sys
from pathlib import Path

# Добавить backend в PYTHONPATH
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

# Настроить Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'eusrr_backend.settings')

import django
django.setup()

from django.conf import settings
from ldap3 import Server, Connection, ALL, SUBTREE, BASE
from ldap3.core.exceptions import LDAPException


def print_header(title):
    """Печать заголовка секции."""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def print_success(message):
    """Печать сообщения об успехе."""
    print(f"✅ {message}")


def print_error(message):
    """Печать сообщения об ошибке."""
    print(f"❌ {message}")


def print_info(message):
    """Печать информационного сообщения."""
    print(f"ℹ️  {message}")


def test_connection_settings():
    """Проверка настроек LDAP из конфигурации Django."""
    print_header("1. Проверка настроек LDAP")
    
    required_settings = [
        'LDAP_ENABLED',
        'LDAP_URI',
        'LDAP_BIND_DN',
        'LDAP_BIND_PASSWORD',
        'LDAP_BASE_DN',
    ]
    
    all_ok = True
    for setting in required_settings:
        value = getattr(settings, setting, None)
        if value:
            # Скрыть пароль
            display_value = '***' if 'PASSWORD' in setting else value
            print_success(f"{setting} = {display_value}")
        else:
            print_error(f"{setting} не настроен!")
            all_ok = False
    
    return all_ok


def test_basic_connection():
    """Проверка базового подключения к LDAP серверу."""
    print_header("2. Проверка базового подключения")
    
    try:
        ldap_host = getattr(settings, 'LDAP_URI', 'ldap://localhost:389')
        print_info(f"Подключение к {ldap_host}...")
        
        server = Server(ldap_host, get_info=ALL)
        conn = Connection(server, auto_bind=True)
        
        print_success("Подключение к LDAP серверу установлено")
        print_info(f"Сервер: {server.info.other.get('vendor_name', ['Unknown'])[0]}")
        print_info(f"Версия: {server.info.other.get('vendor_version', ['Unknown'])[0]}")
        
        conn.unbind()
        return True
        
    except LDAPException as e:
        print_error(f"Ошибка подключения: {e}")
        return False


def test_bind_authentication():
    """Проверка аутентификации с Bind DN."""
    print_header("3. Проверка аутентификации (Bind)")
    
    try:
        ldap_host = getattr(settings, 'LDAP_URI', 'ldap://localhost:389')
        bind_dn = getattr(settings, 'LDAP_BIND_DN', '')
        bind_password = getattr(settings, 'LDAP_BIND_PASSWORD', '')
        
        if not bind_dn or not bind_password:
            print_error("LDAP_BIND_DN или LDAP_BIND_PASSWORD не настроены")
            return False
        
        print_info(f"Аутентификация как: {bind_dn}")
        
        server = Server(ldap_host, get_info=ALL)
        conn = Connection(server, user=bind_dn, password=bind_password, auto_bind=True)
        
        print_success("Аутентификация успешна")
        print_info(f"Связанный DN: {conn.extend.standard.who_am_i()}")
        
        conn.unbind()
        return True
        
    except LDAPException as e:
        print_error(f"Ошибка аутентификации: {e}")
        return False


def test_search_base_dn():
    """Проверка доступа к базовому DN."""
    print_header("4. Проверка доступа к базовому DN")
    
    try:
        ldap_host = getattr(settings, 'LDAP_URI', 'ldap://localhost:389')
        bind_dn = getattr(settings, 'LDAP_BIND_DN', '')
        bind_password = getattr(settings, 'LDAP_BIND_PASSWORD', '')
        base_dn = getattr(settings, 'LDAP_BASE_DN', '')
        
        server = Server(ldap_host)
        conn = Connection(server, user=bind_dn, password=bind_password, auto_bind=True)
        
        print_info(f"Поиск в базовом DN: {base_dn}")
        
        success = conn.search(
            search_base=base_dn,
            search_filter='(objectClass=*)',
            search_scope=BASE,
            attributes=['*']
        )
        
        if success:
            print_success(f"Базовый DN найден: {base_dn}")
            if conn.entries:
                entry = conn.entries[0]
                print_info(f"Атрибуты: {', '.join(entry.entry_attributes)}")
        else:
            print_error(f"Базовый DN не найден: {base_dn}")
            return False
        
        conn.unbind()
        return True
        
    except LDAPException as e:
        print_error(f"Ошибка поиска: {e}")
        return False


def test_search_users():
    """Поиск пользователей в ou=Users."""
    print_header("5. Проверка поиска пользователей")
    
    try:
        ldap_host = getattr(settings, 'LDAP_URI', 'ldap://localhost:389')
        bind_dn = getattr(settings, 'LDAP_BIND_DN', '')
        bind_password = getattr(settings, 'LDAP_BIND_PASSWORD', '')
        users_base = getattr(settings, 'LDAP_USERS_BASE', '')
        
        server = Server(ldap_host)
        conn = Connection(server, user=bind_dn, password=bind_password, auto_bind=True)
        
        print_info(f"Поиск пользователей в: {users_base}")
        
        success = conn.search(
            search_base=users_base,
            search_filter='(&(objectCategory=person)(objectClass=user))',
            search_scope=SUBTREE,
            attributes=['cn', 'mail', 'telephoneNumber', 'employeeNumber', 'sAMAccountName']
        )
        
        if success:
            print_success(f"Найдено пользователей: {len(conn.entries)}")
            for entry in conn.entries[:5]:  # Показать первых 5
                cn = entry.cn.value if hasattr(entry, 'cn') else 'N/A'
                mail = entry.mail.value if hasattr(entry, 'mail') else 'N/A'
                print_info(f"  - {cn} ({mail})")
            if len(conn.entries) > 5:
                print_info(f"  ... и еще {len(conn.entries) - 5}")
        else:
            print_error("Пользователи не найдены")
            return False
        
        conn.unbind()
        return True
        
    except LDAPException as e:
        print_error(f"Ошибка поиска пользователей: {e}")
        return False


def test_search_groups():
    """Поиск групп в ou=Groups."""
    print_header("6. Проверка поиска групп")
    
    try:
        ldap_host = getattr(settings, 'LDAP_URI', 'ldap://localhost:389')
        bind_dn = getattr(settings, 'LDAP_BIND_DN', '')
        bind_password = getattr(settings, 'LDAP_BIND_PASSWORD', '')
        groups_base = getattr(settings, 'LDAP_GROUPS_BASE', '')
        
        server = Server(ldap_host)
        conn = Connection(server, user=bind_dn, password=bind_password, auto_bind=True)
        
        print_info(f"Поиск групп в: {groups_base}")
        
        success = conn.search(
            search_base=groups_base,
            search_filter='(objectClass=groupOfNames)',
            search_scope=SUBTREE,
            attributes=['cn', 'description', 'member']
        )
        
        if success:
            print_success(f"Найдено групп: {len(conn.entries)}")
            for entry in conn.entries:
                cn = entry.cn.value if hasattr(entry, 'cn') else 'N/A'
                desc = entry.description.value if hasattr(entry, 'description') else 'N/A'
                members_count = len(entry.member) if hasattr(entry, 'member') else 0
                print_info(f"  - {cn}: {desc} ({members_count} members)")
        else:
            print_error("Группы не найдены")
            return False
        
        conn.unbind()
        return True
        
    except LDAPException as e:
        print_error(f"Ошибка поиска групп: {e}")
        return False


def test_django_ldap_integration():
    """Проверка интеграции Django с LDAP через employees.ldap."""
    print_header("7. Проверка интеграции Django LDAP")
    
    try:
        print_info("Импорт employees.ldap модулей...")
        from employees.ldap.infrastructure.connections import _ldap
        
        print_success("Модули импортированы успешно")
        
        print_info("Тестирование соединения через _ldap()...")
        with _ldap() as conn:
            base_dn = getattr(settings, 'LDAP_BASE_DN', '')
            success = conn.search(base_dn, '(objectClass=*)', search_scope=BASE)
            
            if success:
                print_success("Соединение через Django LDAP wrapper работает")
                return True
            else:
                print_error("Поиск через Django LDAP wrapper не удался")
                return False
    
    except Exception as e:
        print_error(f"Ошибка интеграции Django LDAP: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_create_test_user():
    """Тест создания тестового пользователя через ORM."""
    print_header("8. Тест создания пользователя (ОПЦИОНАЛЬНО)")
    
    print_info("Этот тест создаст тестового пользователя в LDAP")
    print_info("Пропускаем автоматическое создание - используйте Django shell")
    print_info("Пример:")
    print_info("  from employees.ldap import LdapUser")
    print_info("  user = LdapUser()")
    print_info("  user.cn = 'Test User'")
    print_info("  user.sn = 'User'")
    print_info("  user.save()")
    
    return True


def main():
    """Основная функция - запуск всех тестов."""
    print("\n" + "🔬" * 35)
    print("  ТЕСТИРОВАНИЕ LDAP ПОДКЛЮЧЕНИЯ - EUSRR")
    print("🔬" * 35)
    
    tests = [
        ("Настройки LDAP", test_connection_settings),
        ("Базовое подключение", test_basic_connection),
        ("Аутентификация", test_bind_authentication),
        ("Доступ к базовому DN", test_search_base_dn),
        ("Поиск пользователей", test_search_users),
        ("Поиск групп", test_search_groups),
        ("Интеграция Django LDAP", test_django_ldap_integration),
        ("Создание пользователя", test_create_test_user),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except KeyboardInterrupt:
            print("\n\n⚠️  Тестирование прервано пользователем")
            sys.exit(1)
        except Exception as e:
            print_error(f"Неожиданная ошибка в тесте '{name}': {e}")
            import traceback
            traceback.print_exc()
            results.append((name, False))
    
    # Итоговый отчет
    print_header("ИТОГОВЫЙ ОТЧЕТ")
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}  {name}")
    
    print("\n" + "-" * 70)
    print(f"Результат: {passed}/{total} тестов пройдено")
    print("-" * 70)
    
    if passed == total:
        print("\n🎉 ВСЕ ТЕСТЫ ПРОЙДЕНЫ! LDAP интеграция работает корректно.")
        return 0
    else:
        print(f"\n⚠️  {total - passed} тест(ов) не пройдено. Проверьте конфигурацию.")
        return 1


if __name__ == '__main__':
    sys.exit(main())
