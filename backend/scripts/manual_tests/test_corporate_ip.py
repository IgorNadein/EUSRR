#!/usr/bin/env python
"""Проверка разрешения IP для корпоративной сети 172.11.0.0/16"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'eusrr_backend.settings')

import django
django.setup()

from common.ip_restrictions import is_ip_allowed

print("\n" + "=" * 60)
print("Проверка IP-адресов для корпоративной сети 172.11.0.0/16")
print("=" * 60)

test_ips = [
    ('172.11.0.117', True, 'Ваш текущий IP'),
    ('172.11.0.1', True, 'Корпоративная сеть 172.11.x.x'),
    ('172.11.255.255', True, 'Край диапазона 172.11.x.x'),
    ('172.12.0.1', False, 'За пределами 172.11.x.x'),
    ('172.16.0.1', True, 'Стандартная приватная сеть'),
    ('192.168.1.1', True, 'Локальная сеть'),
    ('10.0.0.1', True, 'Приватная сеть класса A'),
    ('8.8.8.8', False, 'Публичный IP (Google DNS)'),
]

passed = 0
failed = 0

for ip, expected, description in test_ips:
    result = is_ip_allowed(ip)
    status = "✅" if result == expected else "❌"
    
    if result == expected:
        passed += 1
    else:
        failed += 1
    
    result_text = "разрешен" if result else "заблокирован"
    expected_text = "разрешен" if expected else "заблокирован"
    
    print(f"{status} {ip:20} -> {result_text:12} "
          f"(ожидалось: {expected_text:12}) # {description}")

print("\n" + "=" * 60)
if failed == 0:
    print(f"✅ Все тесты пройдены: {passed}/{passed + failed}")
else:
    print(f"⚠️ Тестов пройдено: {passed}/{passed + failed}, провалено: {failed}")
print("=" * 60 + "\n")
