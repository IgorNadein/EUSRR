"""Тест форматирования телефонов для Excel экспорта."""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'eusrr_backend.settings')
django.setup()

from employees.models import Employee
from phonenumbers import format_number, PhoneNumberFormat

print("Тестирование форматирования телефонов...\n")

# Получаем всех сотрудников с телефонами
employees = Employee.objects.exclude(phone_number__isnull=True).exclude(phone_number='')

print(f"Найдено сотрудников с телефонами: {employees.count()}\n")

errors = []
for emp in employees:
    phone_str = ''
    if emp.phone_number:
        try:
            # Пытаемся форматировать
            phone_str = format_number(emp.phone_number, PhoneNumberFormat.INTERNATIONAL)
            print(f"✓ {emp.id}: {emp.last_name} {emp.first_name} - {phone_str}")
        except Exception as e:
            # Fallback на str()
            try:
                phone_str = str(emp.phone_number)
                print(f"⚠ {emp.id}: {emp.last_name} {emp.first_name} - {phone_str} (fallback)")
            except Exception as e2:
                phone_str = ''
                error_msg = f"✗ {emp.id}: {emp.last_name} {emp.first_name} - ERROR: {type(emp.phone_number).__name__} - {e2}"
                print(error_msg)
                errors.append(error_msg)

print(f"\n\nВсего ошибок: {len(errors)}")
if errors:
    print("\nПроблемные записи:")
    for err in errors:
        print(err)
else:
    print("Все телефоны успешно конвертируются!")
