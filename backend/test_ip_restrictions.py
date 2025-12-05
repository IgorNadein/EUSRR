#!/usr/bin/env python
"""
Тестирование IP-ограничений для регистрации.

Запуск:
    python backend/test_ip_restrictions.py
"""
import os
import sys
import django

# Настройка Django
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
os.environ.setdefault("DJANGO_SECRET_KEY", "test-key")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "eusrr_backend.settings")
django.setup()

from common.ip_restrictions import (
    get_client_ip,
    is_local_ip,
    is_ip_allowed,
)


def test_is_local_ip():
    """Тест проверки локальных IP."""
    print("\n=== Тест: is_local_ip ===")
    
    test_cases = [
        ('127.0.0.1', True, 'localhost IPv4'),
        ('127.0.0.100', True, 'localhost range'),
        ('192.168.1.1', True, 'private class C'),
        ('192.168.100.50', True, 'private class C'),
        ('10.0.0.1', True, 'private class A'),
        ('172.16.0.1', True, 'private class B'),
        ('172.31.255.255', True, 'private class B edge'),
        ('8.8.8.8', False, 'public Google DNS'),
        ('203.0.113.50', False, 'public TEST-NET'),
        ('::1', True, 'localhost IPv6'),
        ('invalid-ip', False, 'invalid IP'),
    ]
    
    passed = 0
    failed = 0
    
    for ip, expected, description in test_cases:
        result = is_local_ip(ip)
        status = "✅" if result == expected else "❌"
        
        if result == expected:
            passed += 1
        else:
            failed += 1
        
        print(f"{status} {ip:20} -> {result:5} (expected: {expected:5}) # {description}")
    
    print(f"\nПройдено: {passed}/{passed + failed}")
    return failed == 0


def test_is_ip_allowed():
    """Тест проверки разрешенных IP с кастомными настройками."""
    print("\n=== Тест: is_ip_allowed ===")
    
    # Тест 1: Разрешить все
    print("\n1. Разрешить все IP ['*']:")
    result = is_ip_allowed('203.0.113.50', ['*'])
    print(f"   {'✅' if result else '❌'} 203.0.113.50 -> {result} (expected: True)")
    
    # Тест 2: Разрешить конкретную сеть
    print("\n2. Разрешить сеть 192.168.1.0/24:")
    allowed_net = ['192.168.1.0/24']
    tests = [
        ('192.168.1.1', True),
        ('192.168.1.100', True),
        ('192.168.1.255', True),
        ('192.168.2.1', False),
        ('10.0.0.1', False),
    ]
    
    for ip, expected in tests:
        result = is_ip_allowed(ip, allowed_net)
        status = "✅" if result == expected else "❌"
        print(f"   {status} {ip:20} -> {result:5} (expected: {expected:5})")
    
    # Тест 3: Разрешить конкретные IP
    print("\n3. Разрешить конкретные IP ['192.168.1.100', '10.0.0.5']:")
    allowed_ips = ['192.168.1.100', '10.0.0.5']
    tests = [
        ('192.168.1.100', True),
        ('10.0.0.5', True),
        ('192.168.1.101', False),
        ('10.0.0.6', False),
    ]
    
    for ip, expected in tests:
        result = is_ip_allowed(ip, allowed_ips)
        status = "✅" if result == expected else "❌"
        print(f"   {status} {ip:20} -> {result:5} (expected: {expected:5})")
    
    # Тест 4: По умолчанию (только локальные)
    print("\n4. По умолчанию (None = только локальные IP):")
    tests = [
        ('127.0.0.1', True),
        ('192.168.1.1', True),
        ('10.0.0.1', True),
        ('8.8.8.8', False),
        ('203.0.113.50', False),
    ]
    
    for ip, expected in tests:
        result = is_ip_allowed(ip, None)
        status = "✅" if result == expected else "❌"
        print(f"   {status} {ip:20} -> {result:5} (expected: {expected:5})")


def test_get_client_ip():
    """Тест получения IP из request."""
    print("\n=== Тест: get_client_ip ===")
    
    from django.test import RequestFactory
    
    factory = RequestFactory()
    
    # Тест 1: Обычный запрос
    print("\n1. Обычный запрос (без прокси):")
    request = factory.get('/')
    ip = get_client_ip(request)
    print(f"   IP: {ip}")
    
    # Тест 2: С заголовком X-Forwarded-For
    print("\n2. Запрос через прокси (X-Forwarded-For):")
    request = factory.get('/', HTTP_X_FORWARDED_FOR='203.0.113.50, 192.168.1.1')
    ip = get_client_ip(request)
    expected = '203.0.113.50'
    status = "✅" if ip == expected else "❌"
    print(f"   {status} IP: {ip} (expected: {expected})")
    
    # Тест 3: С одним IP в X-Forwarded-For
    print("\n3. Запрос через прокси (один IP):")
    request = factory.get('/', HTTP_X_FORWARDED_FOR='10.0.0.5')
    ip = get_client_ip(request)
    expected = '10.0.0.5'
    status = "✅" if ip == expected else "❌"
    print(f"   {status} IP: {ip} (expected: {expected})")


def main():
    """Запуск всех тестов."""
    print("=" * 60)
    print("Тестирование модуля IP-ограничений")
    print("=" * 60)
    
    try:
        test_is_local_ip()
        test_is_ip_allowed()
        test_get_client_ip()
        
        print("\n" + "=" * 60)
        print("✅ Все тесты выполнены")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
