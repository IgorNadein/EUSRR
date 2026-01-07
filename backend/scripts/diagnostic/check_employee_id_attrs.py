#!/usr/bin/env python
"""
Скрипт для проверки доступности атрибутов employeeID и employeeNumber в LDAP/AD.

Проверяет:
1. Есть ли эти атрибуты в схеме AD
2. Можно ли записать/прочитать значения
3. Какие ещё ID-подобные атрибуты доступны

Запуск:
    .venv/Scripts/python backend/scripts/diagnostic/check_employee_id_attrs.py
"""
import os
import sys
from pathlib import Path

# Добавляем backend в path для импорта Django settings
backend_path = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(backend_path))

# Настройка Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "eusrr_backend.settings")

import django
django.setup()

from django.conf import settings
from ldap3 import Server, Connection, ALL, SUBTREE, Tls, MODIFY_REPLACE
import ssl


def get_ldap_config():
    """Получает конфигурацию LDAP из Django settings."""
    return {
        "uri": getattr(settings, "LDAP_URI", ""),
        "bind_dn": getattr(settings, "LDAP_BIND_DN", ""),
        "bind_password": getattr(settings, "LDAP_BIND_PASSWORD", ""),
        "base_dn": getattr(settings, "LDAP_BASE_DN", ""),
        "users_base": getattr(settings, "LDAP_USERS_BASE", ""),
        "ca_cert": getattr(settings, "LDAP_TLS_CA_FILE", None),
    }


def connect_ldap(cfg):
    """Создаёт подключение к LDAP."""
    uri = cfg["uri"]
    use_ssl = uri.startswith("ldaps://")
    
    # Парсим хост и порт
    if "://" in uri:
        uri = uri.split("://", 1)[1]
    if ":" in uri:
        host, port = uri.split(":", 1)
        port = int(port)
    else:
        host = uri
        port = 636 if use_ssl else 389
    
    tls = None
    if use_ssl and cfg.get("ca_cert"):
        tls = Tls(
            ca_certs_file=cfg["ca_cert"],
            validate=ssl.CERT_REQUIRED
        )
    elif use_ssl:
        tls = Tls(validate=ssl.CERT_NONE)
    
    server = Server(
        host,
        port=port,
        use_ssl=use_ssl,
        tls=tls,
        get_info=ALL
    )
    
    conn = Connection(
        server,
        user=cfg["bind_dn"],
        password=cfg["bind_password"],
        auto_bind=True
    )
    return conn, server


def check_schema_attributes(server):
    """Проверяет наличие атрибутов в схеме AD."""
    print("\n" + "=" * 80)
    print("1. ПРОВЕРКА СХЕМЫ AD")
    print("=" * 80)
    
    # Атрибуты которые нас интересуют
    target_attrs = [
        "employeeID",
        "employeeNumber", 
        "employeeType",
        "departmentNumber",
        "uid",
        "uidNumber",
    ]
    
    schema_info = server.schema
    if not schema_info:
        print("⚠️  Не удалось получить информацию о схеме")
        return {}
    
    found_attrs = {}
    
    for attr_name in target_attrs:
        # Ищем в attribute types
        attr_def = None
        if hasattr(schema_info, 'attribute_types'):
            attr_def = schema_info.attribute_types.get(attr_name.lower())
            if not attr_def:
                # Попробуем без lower
                attr_def = schema_info.attribute_types.get(attr_name)
        
        if attr_def:
            print(f"\n✅ {attr_name}:")
            print(f"   OID: {attr_def.oid}")
            print(f"   Syntax: {getattr(attr_def, 'syntax', 'N/A')}")
            print(f"   Single-value: {getattr(attr_def, 'single_value', 'N/A')}")
            found_attrs[attr_name] = True
        else:
            print(f"\n❌ {attr_name}: НЕ НАЙДЕН в схеме")
            found_attrs[attr_name] = False
    
    return found_attrs


def find_sample_user(conn, base_dn):
    """Находит первого пользователя для тестирования."""
    conn.search(
        search_base=base_dn,
        search_filter="(&(objectClass=user)(objectCategory=person))",
        search_scope=SUBTREE,
        attributes=["cn", "mail", "sAMAccountName", "employeeID", "employeeNumber"],
        size_limit=5
    )
    
    if conn.entries:
        return conn.entries[0]
    return None


def check_user_attributes(conn, base_dn):
    """Проверяет атрибуты на реальном пользователе."""
    print("\n" + "=" * 80)
    print("2. ПРОВЕРКА АТРИБУТОВ НА ПОЛЬЗОВАТЕЛЯХ")
    print("=" * 80)
    
    user = find_sample_user(conn, base_dn)
    if not user:
        print("⚠️  Не найдено пользователей для проверки")
        return
    
    print(f"\nТестовый пользователь: {user.entry_dn}")
    print(f"CN: {user.cn.value if hasattr(user, 'cn') else 'N/A'}")
    print(f"sAMAccountName: {user.sAMAccountName.value if hasattr(user, 'sAMAccountName') else 'N/A'}")
    
    # Проверяем текущие значения
    for attr in ["employeeID", "employeeNumber"]:
        if hasattr(user, attr) and user[attr].value:
            print(f"\n✅ {attr}: {user[attr].value}")
        else:
            print(f"\n⚠️  {attr}: пусто или не читается")


def check_write_permission(conn, base_dn, cfg):
    """Проверяет возможность записи в атрибуты (на тестовом пользователе)."""
    print("\n" + "=" * 80)
    print("3. ПРОВЕРКА ПРАВ ЗАПИСИ")
    print("=" * 80)
    
    user = find_sample_user(conn, base_dn)
    if not user:
        print("⚠️  Не найдено пользователей для проверки записи")
        return
    
    user_dn = user.entry_dn
    test_value = "TEST_12345"
    
    print(f"\nПопытка записи employeeNumber='{test_value}' в {user_dn}")
    print("⚠️  ВНИМАНИЕ: Это тестовая запись!")
    
    # Спрашиваем подтверждение
    answer = input("\nВыполнить тестовую запись? (yes/no): ").strip().lower()
    if answer != "yes":
        print("Отменено пользователем")
        return
    
    try:
        result = conn.modify(
            user_dn,
            {"employeeNumber": [(MODIFY_REPLACE, [test_value])]}
        )
        
        if result:
            print(f"✅ Запись успешна! employeeNumber = {test_value}")
            
            # Читаем обратно для проверки
            conn.search(
                search_base=user_dn,
                search_filter="(objectClass=*)",
                attributes=["employeeNumber"]
            )
            if conn.entries:
                val = conn.entries[0]["employeeNumber"].value
                print(f"✅ Проверка чтения: employeeNumber = {val}")
            
            # Очищаем тестовое значение
            clean = input("\nОчистить тестовое значение? (yes/no): ").strip().lower()
            if clean == "yes":
                conn.modify(
                    user_dn,
                    {"employeeNumber": [(MODIFY_REPLACE, [])]}
                )
                print("✅ Значение очищено")
        else:
            print(f"❌ Ошибка записи: {conn.result}")
            
    except Exception as e:
        print(f"❌ Исключение при записи: {e}")


def list_all_id_attributes(conn, base_dn):
    """Показывает все атрибуты содержащие 'id' или 'number' у пользователя."""
    print("\n" + "=" * 80)
    print("4. ВСЕ ID-ПОДОБНЫЕ АТРИБУТЫ")
    print("=" * 80)
    
    # Ищем пользователя со всеми атрибутами
    conn.search(
        search_base=base_dn,
        search_filter="(&(objectClass=user)(objectCategory=person))",
        search_scope=SUBTREE,
        attributes=["*"],
        size_limit=1
    )
    
    if not conn.entries:
        print("⚠️  Нет пользователей")
        return
    
    user = conn.entries[0]
    print(f"\nПользователь: {user.entry_dn}\n")
    
    keywords = ["id", "number", "uid", "employee", "guid"]
    
    for attr_name in sorted(user.entry_attributes):
        attr_lower = attr_name.lower()
        if any(kw in attr_lower for kw in keywords):
            value = user[attr_name].value
            if isinstance(value, bytes):
                # GUID или бинарные данные
                if len(value) == 16:
                    import uuid
                    try:
                        guid_str = str(uuid.UUID(bytes_le=value))
                        value = f"(GUID) {guid_str}"
                    except:
                        value = f"<binary {len(value)} bytes>"
                else:
                    value = f"<binary {len(value)} bytes>"
            print(f"  {attr_name:30}: {value}")


def main():
    print("=" * 80)
    print("ПРОВЕРКА АТРИБУТОВ employeeID/employeeNumber в LDAP")
    print("=" * 80)
    
    cfg = get_ldap_config()
    
    print(f"\nКонфигурация:")
    print(f"  URI: {cfg['uri']}")
    print(f"  Bind DN: {cfg['bind_dn']}")
    print(f"  Base DN: {cfg['base_dn']}")
    print(f"  Users Base: {cfg['users_base']}")
    print(f"  CA Cert: {cfg['ca_cert'] or 'не задан'}")
    
    if not cfg["uri"] or not cfg["bind_dn"]:
        print("\n❌ LDAP не настроен! Проверьте переменные окружения.")
        return 1
    
    try:
        print("\nПодключение к LDAP...")
        conn, server = connect_ldap(cfg)
        print(f"✅ Подключено к {cfg['uri']}")
        
        # 1. Проверка схемы
        schema_attrs = check_schema_attributes(server)
        
        # 2. Проверка на пользователях
        search_base = cfg["users_base"] or cfg["base_dn"]
        check_user_attributes(conn, search_base)
        
        # 3. Показать все ID-атрибуты
        list_all_id_attributes(conn, search_base)
        
        # 4. Опционально: тест записи
        print("\n" + "=" * 80)
        answer = input("\nХотите проверить права записи? (yes/no): ").strip().lower()
        if answer == "yes":
            check_write_permission(conn, search_base, cfg)
        
        conn.unbind()
        print("\n✅ Проверка завершена")
        
    except Exception as e:
        print(f"\n❌ Ошибка: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
