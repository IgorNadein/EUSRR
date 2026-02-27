#!/usr/bin/env python
"""
Создаёт HTML файл с рендером страницы отдела для проверки.
"""
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'eusrr_backend.settings')

import django
django.setup()

from django.template import loader, Context
from django.contrib.auth import get_user_model
from employees.models import Department
from django.test import RequestFactory

User = get_user_model()

# Получаем отдел и пользователя
dept = Department.objects.filter(id=16).first()
if not dept:
    dept = Department.objects.first()

user = User.objects.filter(is_superuser=True).first()

if not dept or not user:
    print("Нет данных для рендеринга")
    exit(1)

# Создаём request
factory = RequestFactory()
request = factory.get(f'/employees/departments/{dept.id}/')
request.user = user

# Получаем view context
from employees.views_front import department_detail
response = department_detail(request, pk=dept.id)

# Сохраняем HTML
output_file = 'department_page_render.html'
with open(output_file, 'wb') as f:
    f.write(response.content)

print(f"✓ Страница сохранена в {output_file}")
print(f"  Размер: {len(response.content)} байт")

# Анализ содержимого
html = response.content.decode('utf-8')
print(f"\nАнализ:")
print(f"  <style> тегов: {html.count('<style>')}")
print(f"  <script> тегов: {html.count('<script>')}")
print(f"  .team-wheel: {'✓' if '.team-wheel' in html else '✗'}")
print(f"  .calendar-wrap: {'✓' if '.calendar-wrap' in html else '✗'}")
print(f"  initTeamWheel: {'✓' if 'initTeamWheel' in html else '✗'}")
print(f"  FullCalendar: {'✓' if 'FullCalendar' in html else '✗'}")
print(f"  dropdown-toggle: {'✓' if 'dropdown-toggle' in html else '✗'}")
print(f"  Bootstrap JS: {'✓' if 'bootstrap.bundle.min.js' in html else '✗'}")
