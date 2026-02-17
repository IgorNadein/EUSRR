#!/usr/bin/env python
"""Тест модернизированной системы логирования."""

import os
import sys

# Добавляем backend в путь
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'eusrr_backend.settings')

import django
django.setup()

import logging

# Тестируем разные логгеры
print("=" * 70)
print("ТЕСТ МОДЕРНИЗИРОВАННОЙ СИСТЕМЫ ЛОГИРОВАНИЯ")
print("=" * 70)

# 1. Логгер employees
print("\n1. Тест логгера 'employees':")
employees_logger = logging.getLogger('employees')
employees_logger.debug('Тестовое DEBUG сообщение')
employees_logger.info('Тестовое INFO сообщение')
employees_logger.warning('Тестовое WARNING сообщение')
employees_logger.error('Тестовое ERROR сообщение')

# 2. Логгер security
print("\n2. Тест логгера 'employees.ldap' (security):")
ldap_logger = logging.getLogger('employees.ldap')
ldap_logger.info('LDAP аутентификация успешна', extra={'username': 'test_user'})
ldap_logger.warning('LDAP подключение медленное', extra={'latency': '1000ms'})

# 3. Логгер с исключением
print("\n3. Тест логирования исключений:")
try:
    result = 10 / 0
except ZeroDivisionError:
    employees_logger.exception('Тестовое исключение для демонстрации трассировки')

# 4. Django логгер
print("\n4. Тест Django логгера:")
django_logger = logging.getLogger('django')
django_logger.info('Django логгер работает')

print("\n" + "=" * 70)
print("✓ Все логгеры протестированы!")
print("=" * 70)

# Проверяем созданные файлы
logs_dir = os.path.join(os.path.dirname(__file__), 'logs')
if os.path.exists(logs_dir):
    log_files = [f for f in os.listdir(logs_dir) if f.endswith('.log')]
    print(f"\n📁 Найдено файлов логов: {len(log_files)}")
    for log_file in sorted(log_files):
        file_path = os.path.join(logs_dir, log_file)
        file_size = os.path.getsize(file_path)
        print(f"   - {log_file:20s} ({file_size:,} bytes)")
else:
    print("\n⚠ Директория logs/ не найдена")

print("\n💡 Проверьте содержимое файлов:")
print("   tail -f backend/logs/all.log")
print("   tail -f backend/logs/error.log")
print("   tail -f backend/logs/security.log")
