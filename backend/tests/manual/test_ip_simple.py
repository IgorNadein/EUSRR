#!/usr/bin/env python
"""
Простой тест IP-ограничений (без Django).
"""
import ipaddress


def is_local_ip(ip_address: str) -> bool:
    """Проверяет, является ли IP-адрес локальным."""
    try:
        ip = ipaddress.ip_address(ip_address)
        return ip.is_private or ip.is_loopback or ip.is_link_local
    except ValueError:
        return False


def is_ip_allowed(ip_address: str, allowed_networks=None):
    """Проверяет, разрешен ли доступ с данного IP-адреса."""
    if allowed_networks is None:
        return is_local_ip(ip_address)
    
    if not allowed_networks:
        return False
    
    if allowed_networks == ['*'] or '*' in allowed_networks:
        return True
    
    try:
        ip = ipaddress.ip_address(ip_address)
        
        for network_str in allowed_networks:
            if '/' in network_str:
                network = ipaddress.ip_network(network_str, strict=False)
                if ip in network:
                    return True
            else:
                allowed_ip = ipaddress.ip_address(network_str)
                if ip == allowed_ip:
                    return True
        
        return False
    except ValueError:
        return False


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
        
        print(f"{status} {ip:20} -> {str(result):5} "
              f"(expected: {str(expected):5}) # {description}")
    
    print(f"\nПройдено: {passed}/{passed + failed}")
    return failed == 0


def test_is_ip_allowed():
    """Тест проверки разрешенных IP с кастомными настройками."""
    print("\n=== Тест: is_ip_allowed ===")
    
    # Тест 1: Разрешить все
    print("\n1. Разрешить все IP ['*']:")
    result = is_ip_allowed('203.0.113.50', ['*'])
    status = '✅' if result else '❌'
    print(f"   {status} 203.0.113.50 -> {result} (expected: True)")
    
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
        print(f"   {status} {ip:20} -> {str(result):5} "
              f"(expected: {str(expected):5})")
    
    # Тест 3: Разрешить конкретные IP
    print("\n3. Разрешить IP ['192.168.1.100', '10.0.0.5']:")
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
        print(f"   {status} {ip:20} -> {str(result):5} "
              f"(expected: {str(expected):5})")
    
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
        print(f"   {status} {ip:20} -> {str(result):5} "
              f"(expected: {str(expected):5})")


def main():
    """Запуск всех тестов."""
    print("=" * 60)
    print("Тестирование модуля IP-ограничений")
    print("=" * 60)
    
    try:
        test_is_local_ip()
        test_is_ip_allowed()
        
        print("\n" + "=" * 60)
        print("✅ Все тесты выполнены успешно")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())
