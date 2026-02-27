"""
Скрипт для создания тестовых пользователей в корпоративном портале.
Создает 100+ пользователей с разными ролями и отделами.
"""
import os
import sys
from pathlib import Path

# Добавляем путь к backend в sys.path
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

import django
from datetime import date, timedelta
import random

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'eusrr_backend.settings')
django.setup()

from django.contrib.auth import get_user_model
from employees.models import Department, Position, EmployeeDepartment

User = get_user_model()

# Списки для генерации данных
FIRST_NAMES = [
    'Александр', 'Дмитрий', 'Максим', 'Сергей', 'Андрей', 'Алексей', 'Артем', 'Илья',
    'Кирилл', 'Михаил', 'Иван', 'Даниил', 'Егор', 'Никита', 'Матвей', 'Роман',
    'Владислав', 'Ярослав', 'Тимофей', 'Владимир', 'Павел', 'Николай', 'Денис', 'Олег',
    'Анна', 'Мария', 'Елена', 'Ольга', 'Татьяна', 'Наталья', 'Екатерина', 'Ирина',
    'Юлия', 'Светлана', 'Людмила', 'Галина', 'Анастасия', 'Дарья', 'Виктория', 'Валерия',
    'Ксения', 'Полина', 'Алина', 'Вероника', 'София', 'Марина', 'Оксана', 'Алла'
]

LAST_NAMES = [
    'Иванов', 'Петров', 'Сидоров', 'Смирнов', 'Кузнецов', 'Попов', 'Васильев', 'Соколов',
    'Михайлов', 'Новиков', 'Федоров', 'Морозов', 'Волков', 'Алексеев', 'Лебедев', 'Семенов',
    'Егоров', 'Павлов', 'Козлов', 'Степанов', 'Николаев', 'Орлов', 'Андреев', 'Макаров',
    'Никитин', 'Захаров', 'Зайцев', 'Соловьев', 'Борисов', 'Яковлев', 'Григорьев', 'Романов',
    'Воробьев', 'Сергеев', 'Фролов', 'Дмитриев', 'Ковалев', 'Белов', 'Комаров', 'Жуков',
    'Иванова', 'Петрова', 'Сидорова', 'Смирнова', 'Кузнецова', 'Попова', 'Васильева', 'Соколова'
]

PATRONYMICS = [
    'Александрович', 'Дмитриевич', 'Максимович', 'Сергеевич', 'Андреевич', 'Алексеевич',
    'Артемович', 'Ильич', 'Кириллович', 'Михайлович', 'Иванович', 'Даниилович',
    'Александровна', 'Дмитриевна', 'Максимовна', 'Сергеевна', 'Андреевна', 'Алексеевна',
    'Артемовна', 'Ильинична', 'Кирилловна', 'Михайловна', 'Ивановна', 'Данииловна'
]

DEPARTMENTS_DATA = [
    {'name': 'Разработка', 'code': 'DEV'},
    {'name': 'Тестирование', 'code': 'QA'},
    {'name': 'Продажи', 'code': 'SALES'},
    {'name': 'Маркетинг', 'code': 'MKT'},
    {'name': 'HR', 'code': 'HR'},
    {'name': 'Финансы', 'code': 'FIN'},
    {'name': 'Бухгалтерия', 'code': 'ACC'},
    {'name': 'Логистика', 'code': 'LOG'},
    {'name': 'Производство', 'code': 'PROD'},
    {'name': 'Закупки', 'code': 'PURCH'},
]

POSITIONS_DATA = [
    'Младший специалист',
    'Специалист',
    'Старший специалист',
    'Ведущий специалист',
    'Менеджер',
    'Старший менеджер',
    'Руководитель группы',
    'Руководитель отдела',
    'Директор',
    'Стажер',
]


def create_departments():
    """Создание отделов"""
    print('\n📁 Создание отделов...')
    departments = []
    for dept_data in DEPARTMENTS_DATA:
        dept, created = Department.objects.get_or_create(
            name=dept_data['name'],
            defaults={'description': f'Отдел {dept_data["name"]}'}
        )
        departments.append(dept)
        if created:
            print(f'  ✅ Создан отдел: {dept.name}')
        else:
            print(f'  ℹ️  Отдел существует: {dept.name}')
    return departments


def create_positions():
    """Создание должностей"""
    print('\n💼 Создание должностей...')
    positions = []
    for pos_name in POSITIONS_DATA:
        pos, created = Position.objects.get_or_create(
            name=pos_name
        )
        positions.append(pos)
        if created:
            print(f'  ✅ Создана должность: {pos.name}')
    return positions


def generate_email(first_name, last_name, counter):
    """Генерация email"""
    first = first_name.lower()
    last = last_name.lower()
    
    # Транслитерация
    translit = {
        'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'e',
        'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm',
        'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u',
        'ф': 'f', 'х': 'h', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'sch', 'ъ': '',
        'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya'
    }
    
    first_en = ''.join(translit.get(c, c) for c in first)
    last_en = ''.join(translit.get(c, c) for c in last)
    
    return f'{first_en}.{last_en}{counter}@company.local'


def generate_phone():
    """Генерация номера телефона"""
    return f'+7{random.randint(900, 999)}{random.randint(1000000, 9999999)}'


def generate_birthdate():
    """Генерация даты рождения (25-65 лет)"""
    years_ago = random.randint(25, 65)
    days_offset = random.randint(0, 364)
    return date.today() - timedelta(days=years_ago * 365 + days_offset)


def create_users(count=120, departments=None, positions=None):
    """Создание пользователей"""
    print(f'\n👥 Создание {count} пользователей...')
    
    if not departments:
        departments = list(Department.objects.all())
    if not positions:
        positions = list(Position.objects.all())
    
    created_count = 0
    skipped_count = 0
    
    for i in range(1, count + 1):
        first_name = random.choice(FIRST_NAMES)
        last_name = random.choice(LAST_NAMES)
        patronymic = random.choice(PATRONYMICS)
        
        email = generate_email(first_name, last_name, i)
        
        # Проверяем, существует ли пользователь
        if User.objects.filter(email=email).exists():
            skipped_count += 1
            continue
        
        try:
            # Создаем пользователя
            user = User.objects.create_user(
                email=email,
                password='test123',  # Простой пароль для тестирования
                first_name=first_name,
                last_name=last_name,
                patronymic=patronymic,
                phone_number=generate_phone(),
                birth_date=generate_birthdate(),
                is_active=True,
                email_verified=True,
                is_staff=random.random() < 0.1,  # 10% - staff
                send_activation_email=False
            )
            
            # Назначаем должность
            position = random.choice(positions)
            user.position = position
            user.save()
            
            # Назначаем отдел(ы)
            # 70% - один отдел, 25% - два отдела, 5% - три отдела
            dept_count = random.choices([1, 2, 3], weights=[70, 25, 5])[0]
            user_departments = random.sample(departments, min(dept_count, len(departments)))
            
            for dept in user_departments:
                EmployeeDepartment.objects.create(
                    employee=user,
                    department=dept,
                    is_active=True
                )
            
            created_count += 1
            
            if created_count % 10 == 0:
                print(f'  ✅ Создано {created_count} пользователей...')
                
        except Exception as e:
            print(f'  ❌ Ошибка создания пользователя {email}: {e}')
            skipped_count += 1
    
    return created_count, skipped_count


def print_statistics():
    """Вывод статистики"""
    print('\n' + '=' * 60)
    print('📊 СТАТИСТИКА БАЗЫ ДАННЫХ')
    print('=' * 60)
    
    total_users = User.objects.count()
    active_users = User.objects.filter(is_active=True).count()
    staff_users = User.objects.filter(is_staff=True).count()
    
    print(f'\n👥 Пользователи:')
    print(f'   Всего: {total_users}')
    print(f'   Активных: {active_users}')
    print(f'   Персонал: {staff_users}')
    
    departments = Department.objects.all()
    print(f'\n📁 Отделы: {departments.count()}')
    for dept in departments:
        emp_count = EmployeeDepartment.objects.filter(
            department=dept,
            is_active=True
        ).count()
        print(f'   • {dept.name}: {emp_count} сотрудников')
    
    positions = Position.objects.all()
    print(f'\n💼 Должности: {positions.count()}')
    for pos in positions:
        emp_count = User.objects.filter(position=pos).count()
        if emp_count > 0:
            print(f'   • {pos.name}: {emp_count} сотрудников')
    
    print('\n' + '=' * 60)


def main():
    print('=' * 60)
    print('🚀 ГЕНЕРАЦИЯ ТЕСТОВЫХ ПОЛЬЗОВАТЕЛЕЙ')
    print('=' * 60)
    
    # Создаем отделы и должности
    departments = create_departments()
    positions = create_positions()
    
    # Создаем пользователей
    created, skipped = create_users(
        count=120,
        departments=departments,
        positions=positions
    )
    
    print(f'\n✅ Создание завершено!')
    print(f'   Создано: {created} пользователей')
    if skipped > 0:
        print(f'   Пропущено: {skipped} (уже существуют)')
    
    # Выводим статистику
    print_statistics()
    
    print('\n💡 Данные для входа:')
    print('   Username: user001, user002, ... user120')
    print('   Password: test123')
    print('   Email: имя.фамилия1@company.local, и т.д.')
    print('\n' + '=' * 60)


if __name__ == '__main__':
    main()
