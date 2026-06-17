#!/usr/bin/env python
"""
Скрипт для проверки записи пользователя в LDAP
"""
import sys
import os
from ldap3 import Server, Connection, ALL, SUBTREE, Tls
import ssl

# Connection settings are read from environment variables.
LDAP_URI = os.getenv("LDAP_SERVER_URI", "ldaps://ldap.example.local:636")
LDAP_BIND_DN = os.getenv("LDAP_BIND_DN", "user@example.local")
LDAP_BIND_PASSWORD = os.getenv("LDAP_BIND_PASSWORD", "")
LDAP_BASE_DN = os.getenv("LDAP_BASE_DN", "DC=example,DC=local")
LDAP_USERS_BASE = os.getenv("LDAP_USERS_BASE", "OU=Users,DC=example,DC=local")
LDAP_CA_CERT = os.getenv("LDAP_CA_CERT", "corp-ca.pem")

# Email пользователя для поиска
USER_EMAIL = "nadein-igor-vladimirovich@05-04-1999.ru"

def main():
    if not LDAP_BIND_PASSWORD:
        print("LDAP_BIND_PASSWORD environment variable is required")
        sys.exit(1)

    print(f"=" * 80)
    print(f"Подключение к LDAP: {LDAP_URI}")
    print(f"Bind DN: {LDAP_BIND_DN}")
    print(f"=" * 80)
    
    try:
        # Настройка TLS
        tls = Tls(
            ca_certs_file=LDAP_CA_CERT,
            validate=ssl.CERT_REQUIRED
        )
        
        # Подключение к серверу
        server = Server(
            "DCII.robotail.local",
            port=636,
            use_ssl=True,
            tls=tls,
            get_info=ALL
        )
        
        conn = Connection(
            server,
            user=LDAP_BIND_DN,
            password=change-me-redacted-secret
            auto_bind=True
        )
        
        print(f"✅ Успешное подключение к LDAP")
        print(f"Server info: {server.info}")
        print(f"\n" + "=" * 80)
        print(f"Поиск пользователя с email: {USER_EMAIL}")
        print(f"=" * 80)
        
        # Поиск пользователя по email
        search_filter = f"(&(objectClass=user)(mail={USER_EMAIL}))"
        
        conn.search(
            search_base=LDAP_BASE_DN,
            search_filter=search_filter,
            search_scope=SUBTREE,
            attributes=['*']  # Получаем все атрибуты
        )
        
        if not conn.entries:
            print(f"❌ Пользователь с email {USER_EMAIL} не найден в LDAP")
            
            # Попробуем поиск по userPrincipalName
            print(f"\nПоиск по userPrincipalName...")
            upn_filter = f"(&(objectClass=user)(userPrincipalName=*{USER_EMAIL.split('@')[0]}*))"
            conn.search(
                search_base=LDAP_BASE_DN,
                search_filter=upn_filter,
                search_scope=SUBTREE,
                attributes=['*']
            )
            
            if not conn.entries:
                print(f"❌ Не найдено по userPrincipalName")
                
                # Поиск по sAMAccountName
                print(f"\nПоиск по sAMAccountName...")
                sam_filter = f"(&(objectClass=user)(sAMAccountName=*nadein*))"
                conn.search(
                    search_base=LDAP_BASE_DN,
                    search_filter=sam_filter,
                    search_scope=SUBTREE,
                    attributes=['*']
                )
                
                if not conn.entries:
                    print(f"❌ Не найдено записей с 'nadein' в sAMAccountName")
                else:
                    print(f"\n✅ Найдено записей: {len(conn.entries)}")
            else:
                print(f"\n✅ Найдено записей: {len(conn.entries)}")
        else:
            print(f"\n✅ Найдено записей: {len(conn.entries)}")
        
        # Выводим все найденные записи
        for idx, entry in enumerate(conn.entries, 1):
            print(f"\n{'=' * 80}")
            print(f"ЗАПИСЬ #{idx}")
            print(f"{'=' * 80}")
            print(f"DN: {entry.entry_dn}")
            print(f"\nАтрибуты:")
            print(f"-" * 80)
            
            # Основные атрибуты
            important_attrs = [
                'cn', 'givenName', 'sn', 'displayName', 'mail',
                'userPrincipalName', 'sAMAccountName', 'objectGUID',
                'telephoneNumber', 'mobile', 'userAccountControl',
                'whenCreated', 'whenChanged', 'memberOf', 'thumbnailPhoto'
            ]
            
            for attr in important_attrs:
                if hasattr(entry, attr):
                    value = getattr(entry, attr).value
                    if attr == 'thumbnailPhoto' and value:
                        print(f"  {attr:25}: <binary data, length={len(value)} bytes>")
                    elif attr == 'memberOf' and value:
                        print(f"  {attr:25}:")
                        if isinstance(value, list):
                            for group in value:
                                print(f"    - {group}")
                        else:
                            print(f"    - {value}")
                    elif attr == 'objectGUID' and value:
                        # Преобразуем GUID в читаемый формат
                        guid_bytes = value
                        if isinstance(guid_bytes, bytes):
                            guid_str = '-'.join([
                                guid_bytes[3::-1].hex(),
                                guid_bytes[5:3:-1].hex(),
                                guid_bytes[7:5:-1].hex(),
                                guid_bytes[8:10].hex(),
                                guid_bytes[10:].hex()
                            ])
                            print(f"  {attr:25}: {guid_str}")
                        else:
                            print(f"  {attr:25}: {value}")
                    else:
                        print(f"  {attr:25}: {value}")
            
            # Дополнительные атрибуты
            print(f"\n  Все остальные атрибуты:")
            for attr_name in entry.entry_attributes:
                if attr_name not in important_attrs:
                    value = entry[attr_name].value
                    if isinstance(value, bytes):
                        print(f"    {attr_name:23}: <binary data, length={len(value)} bytes>")
                    else:
                        print(f"    {attr_name:23}: {value}")
        
        conn.unbind()
        print(f"\n{'=' * 80}")
        print(f"✅ Проверка завершена")
        print(f"{'=' * 80}")
        
    except Exception as e:
        print(f"\n❌ Ошибка: {type(e).__name__}")
        print(f"   {str(e)}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
