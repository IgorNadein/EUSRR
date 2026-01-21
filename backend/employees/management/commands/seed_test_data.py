"""
Management команда для заполнения БД тестовыми данными
Использование: python manage.py seed_test_data [--admin-username USERNAME]
"""
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.db import transaction
from employees.models import Department, Position, Employee, Skill
from datetime import datetime, timedelta
import random

User = get_user_model()


class Command(BaseCommand):
    help = 'Заполняет БД тестовыми данными и создает администратора'

    def add_arguments(self, parser):
        parser.add_argument(
            '--admin-email',
            type=str,
            default='igor@example.com',
            help='Email администратора (используется как логин)'
        )
        parser.add_argument(
            '--admin-phone',
            type=str,
            default='+79991234567',
            help='Телефон администратора'
        )
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Очистить существующие данные перед заполнением'
        )

    @transaction.atomic
    def handle(self, *args, **options):
        admin_email = options['admin_email']
        admin_phone = options['admin_phone']
        clear_data = options.get('clear', False)

        if clear_data:
            self.stdout.write(self.style.WARNING('Очистка существующих данных...'))
            Employee.objects.all().delete()
            Position.objects.all().delete()
            Department.objects.all().delete()
            Skill.objects.all().delete()

        # 1. Создаем/обновляем администратора
        self.stdout.write(self.style.SUCCESS(f'\n1. Создание администратора: {admin_email}'))
        
        admin_user, created = User.objects.update_or_create(
            email=admin_email,
            defaults={
                'phone_number': admin_phone,
                'is_staff': True,
                'is_superuser': True,
                'is_active': True,
                'email_verified': True,
                'first_name': 'Игорь',
                'last_name': 'Администратор',
                'patronymic': 'Владимирович',
            }
        )
        
        if created:
            admin_user.set_password('admin123')
            admin_user.save()
            self.stdout.write(self.style.SUCCESS(
                f'✓ Создан новый администратор: {admin_email}\n'
                f'  Пароль: admin123'
            ))
        else:
            # Обновляем права у существующего
            admin_user.is_staff = True
            admin_user.is_superuser = True
            admin_user.is_active = True
            admin_user.email_verified = True
            admin_user.save()
            self.stdout.write(self.style.WARNING(
                f'✓ Администратор {admin_email} обновлен'
            ))

        # Убираем права администратора у всех остальных
        User.objects.exclude(email=admin_email).update(
            is_staff=False, 
            is_superuser=False
        )
        self.stdout.write(self.style.SUCCESS(
            f'✓ {admin_email} - единственный администратор\n'
        ))

        # 2. Создаем отделы
        self.stdout.write(self.style.SUCCESS('2. Создание отделов'))
        departments = []
        dept_names = [
            'IT-отдел',
            'Отдел разработки',
            'Отдел поддержки',
            'HR-отдел',
            'Финансовый отдел',
            'Отдел продаж',
        ]
        
        for name in dept_names:
            dept, created = Department.objects.get_or_create(
                name=name,
                defaults={'description': f'Описание {name}'}
            )
            departments.append(dept)
            status = '✓ Создан' if created else '- Существует'
            self.stdout.write(f'  {status}: {name}')

        # 3. Создаем должности
        self.stdout.write(self.style.SUCCESS('\n3. Создание должностей'))
        positions = []
        position_names = [
            'Директор',
            'Руководитель отдела',
            'Ведущий разработчик',
            'Разработчик',
            'Junior разработчик',
            'Системный администратор',
            'Специалист техподдержки',
            'HR-менеджер',
            'Бухгалтер',
            'Менеджер по продажам',
        ]
        
        for name in position_names:
            pos, created = Position.objects.get_or_create(name=name)
            positions.append(pos)
            status = '✓ Создан' if created else '- Существует'
            self.stdout.write(f'  {status}: {name}')

        # 4. Создаем навыки
        self.stdout.write(self.style.SUCCESS('\n4. Создание навыков'))
        skills = []
        skill_names = [
            'Python', 'Django', 'JavaScript', 'React', 'PostgreSQL',
            'Docker', 'Git', 'REST API', 'WebSocket', 'Redis',
            'Celery', 'LDAP', 'Linux', 'HTML/CSS', 'SCSS',
        ]
        
        for name in skill_names:
            skill, created = Skill.objects.get_or_create(name=name)
            skills.append(skill)
            status = '✓ Создан' if created else '- Существует'
            self.stdout.write(f'  {status}: {name}')

        # 5. Создаем сотрудников
        self.stdout.write(self.style.SUCCESS('\n5. Создание тестовых сотрудников'))
        
        # Обновляем администратора - добавляем должность
        admin_user.position = positions[0]  # Директор
        admin_user.birth_date = datetime(1990, 1, 1).date()
        admin_user.save()
        
        # Добавляем администратора в IT-отдел как руководителя
        from employees.models import EmployeeDepartment
        EmployeeDepartment.objects.get_or_create(
            employee=admin_user,
            department=departments[0],
            defaults={'is_active': True}
        )
        departments[0].head = admin_user
        departments[0].save()
        
        # Добавляем навыки администратору
        admin_user.skills.set(random.sample(skills, min(5, len(skills))))
        self.stdout.write(f'  ✓ Обновлен профиль администратора')
        
        # Тестовые сотрудники
        test_employees = [
            ('Анна', 'Иванова', 'Петровна', 'anna.ivanova', '+79991234501'),
            ('Петр', 'Сидоров', 'Иванович', 'petr.sidorov', '+79991234502'),
            ('Мария', 'Петрова', 'Сергеевна', 'maria.petrova', '+79991234503'),
            ('Алексей', 'Смирнов', 'Александрович', 'alex.smirnov', '+79991234504'),
            ('Елена', 'Козлова', 'Дмитриевна', 'elena.kozlova', '+79991234505'),
            ('Дмитрий', 'Морозов', 'Павлович', 'dmitry.morozov', '+79991234506'),
            ('Ольга', 'Новикова', 'Андреевна', 'olga.novikova', '+79991234507'),
            ('Сергей', 'Волков', 'Николаевич', 'sergey.volkov', '+79991234508'),
            ('Наталья', 'Соколова', 'Викторовна', 'natalia.sokolova', '+79991234509'),
            ('Андрей', 'Лебедев', 'Михайлович', 'andrey.lebedev', '+79991234510'),
        ]
        
        created_count = 0
        for first_name, last_name, patronymic, username, phone in test_employees:
            email = f'{username}@example.com'
            
            # Создаем User
            user, user_created = User.objects.get_or_create(
                email=email,
                defaults={
                    'phone_number': phone,
                    'first_name': first_name,
                    'last_name': last_name,
                    'patronymic': patronymic,
                    'is_active': True,
                    'email_verified': True,
                    'birth_date': datetime(1985 + random.randint(0, 20), random.randint(1, 12), random.randint(1, 28)).date(),
                    'position': random.choice(positions[2:]),
                }
            )
            if user_created:
                user.set_password('test123')
                # Добавляем случайные навыки
                user.skills.set(random.sample(skills, random.randint(3, 7)))
                user.save()
                
                # Добавляем в случайный отдел
                dept = random.choice(departments)
                EmployeeDepartment.objects.create(
                    employee=user,
                    department=dept,
                    is_active=True
                )
                
                created_count += 1
                self.stdout.write(f'  ✓ {first_name} {last_name}')

        # Итоговая статистика
        self.stdout.write(self.style.SUCCESS('\n' + '='*60))
        self.stdout.write(self.style.SUCCESS('✓ Заполнение БД завершено!'))
        self.stdout.write(self.style.SUCCESS('='*60))
        self.stdout.write(f'\nСоздано объектов:')
        self.stdout.write(f'  • Отделов: {Department.objects.count()}')
        self.stdout.write(f'  • Должностей: {Position.objects.count()}')
        self.stdout.write(f'  • Навыков: {Skill.objects.count()}')
        self.stdout.write(f'  • Пользователей: {User.objects.count()}')
        
        self.stdout.write(self.style.SUCCESS(f'\n🔐 Администратор:'))
        self.stdout.write(f'  Email (логин): {admin_email}')
        if created:
            self.stdout.write(f'  Пароль: admin123')
        
        self.stdout.write(self.style.WARNING(f'\n👥 Тестовые пользователи:'))
        self.stdout.write(f'  Логин: <username>@example.com')
        self.stdout.write(f'  Пароль для всех: test123')
        self.stdout.write('')
