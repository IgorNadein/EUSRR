"""
Management command для создания тестовых пользователей с календарями.
"""

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from schedule.models import Calendar, Event
from datetime import datetime, timedelta
from django.utils import timezone

User = get_user_model()


class Command(BaseCommand):
    help = "Создание тестовых пользователей и календарей для системы schedule"

    def add_arguments(self, parser):
        parser.add_argument(
            "--clean",
            action="store_true",
            help=(
                "Удалить существующих тестовых пользователей и "
                "календари перед созданием новых"
            ),
        )

    def handle(self, *args, **options):
        # Удаление существующих данных если указан флаг --clean
        if options["clean"]:
            self.stdout.write(
                self.style.WARNING(
                    "\nУдаление существующих тестовых данных...\n"
                )
            )

            # Список тестовых пользователей для удаления
            test_usernames = ["anna_ivanova", "petr_petrov", "maria_sidorova"]

            for username in test_usernames:
                try:
                    user = User.objects.get(username=username)
                    # Сначала удаляем события в календарях пользователя
                    from schedule.models import CalendarRelation
                    from django.contrib.contenttypes.models import ContentType

                    ct = ContentType.objects.get_for_model(User)
                    calendar_relations = CalendarRelation.objects.filter(
                        content_type=ct, object_id=user.id, distinction="owner"
                    )

                    for rel in calendar_relations:
                        calendar = rel.calendar
                        events_count = calendar.event_set.count()
                        calendar.event_set.all().delete()
                        calendar.delete()
                        self.stdout.write(
                            f"  Удален календарь: {calendar.name} ({
                                events_count
                            } событий)"
                        )

                    user.delete()
                    self.stdout.write(
                        self.style.SUCCESS(f"  Удален пользователь: {username}")
                    )
                except User.DoesNotExist:
                    self.stdout.write(
                        f"  Пользователь {username} не найден (пропуск)"
                    )

            # Удаляем календари по slug (если они остались)
            calendar_slugs = [
                "anna-work",
                "anna-personal",
                "petr-projects",
                "petr-meetings",
                "maria-calendar",
            ]
            for slug in calendar_slugs:
                try:
                    calendar = Calendar.objects.get(slug=slug)
                    events_count = calendar.event_set.count()
                    calendar.event_set.all().delete()
                    calendar.delete()
                    self.stdout.write(
                        f"  Удален календарь: {slug} ({events_count} событий)"
                    )
                except Calendar.DoesNotExist:
                    pass

            self.stdout.write(self.style.SUCCESS("\nОчистка завершена!\n"))

        self.stdout.write("Создание тестовых пользователей и календарей...\n")

        # Создание пользователей
        test_users = [
            {
                "username": "anna_ivanova",
                "email": "anna@example.com",
                "first_name": "Анна",
                "last_name": "Иванова",
                "password": "test123",
                "phone_number": "+7900111222",
            },
            {
                "username": "petr_petrov",
                "email": "petr@example.com",
                "first_name": "Петр",
                "last_name": "Петров",
                "password": "test123",
                "phone_number": "+7900222333",
            },
            {
                "username": "maria_sidorova",
                "email": "maria@example.com",
                "first_name": "Мария",
                "last_name": "Сидорова",
                "password": "test123",
                "phone_number": "+7900333444",
            },
        ]

        created_users = []
        for user_data in test_users:
            user, created = User.objects.get_or_create(
                username=user_data["username"],
                defaults={
                    "email": user_data["email"],
                    "first_name": user_data["first_name"],
                    "last_name": user_data["last_name"],
                    "phone_number": user_data["phone_number"],
                },
            )
            if created:
                user.set_password(user_data["password"])
                # Автоматически подтверждаем email для тестовых пользователей
                user.email_verified = True
                user.save()
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Создан пользователь: {user.get_full_name()} ({
                            user.username
                        })"
                    )
                )
            else:
                self.stdout.write(
                    self.style.WARNING(
                        f"Пользователь уже существует: {user.get_full_name()} ({
                            user.username
                        })"
                    )
                )
            created_users.append(user)

        # Создание календарей с привязкой к владельцам
        calendar_data = [
            {
                "name": "Рабочий календарь Анны",
                "slug": "anna-work",
                "owner_idx": 0,
            },  # anna_ivanova
            {
                "name": "Личные дела Анны",
                "slug": "anna-personal",
                "owner_idx": 0,
            },
            {
                "name": "Проекты Петра",
                "slug": "petr-projects",
                "owner_idx": 1,
            },  # petr_petrov
            {"name": "Встречи Петра", "slug": "petr-meetings", "owner_idx": 1},
            {
                "name": "Календарь Марии",
                "slug": "maria-calendar",
                "owner_idx": 2,
            },  # maria_sidorova
        ]

        created_calendars = []
        for cal_data in calendar_data:
            calendar, created = Calendar.objects.get_or_create(
                slug=cal_data["slug"], defaults={"name": cal_data["name"]}
            )
            if created:
                self.stdout.write(
                    self.style.SUCCESS(f"Создан календарь: {calendar.name}")
                )
                # Создаем CalendarRelation с owner
                owner = created_users[cal_data["owner_idx"]]
                calendar.create_relation(
                    owner, distinction="owner", inheritable=True
                )
                self.stdout.write(f"  Владелец: {owner.get_full_name()}")
            else:
                self.stdout.write(
                    self.style.WARNING(
                        f"Календарь уже существует: {calendar.name}"
                    )
                )
            created_calendars.append(calendar)

        # Создание событий
        now = timezone.now()
        today = now.date()

        events_data = [
            # События для Анны (календарь 0 - рабочий)
            {
                "calendar": created_calendars[0],
                "title": "Встреча с клиентом",
                "start": datetime.combine(
                    today + timedelta(days=1),
                    datetime.min.time().replace(hour=10),
                ),
                "end": datetime.combine(
                    today + timedelta(days=1),
                    datetime.min.time().replace(hour=11),
                ),
                "description": "Обсуждение проекта",
            },
            {
                "calendar": created_calendars[0],
                "title": "Планерка команды",
                "start": datetime.combine(
                    today + timedelta(days=2),
                    datetime.min.time().replace(hour=9),
                ),
                "end": datetime.combine(
                    today + timedelta(days=2),
                    datetime.min.time().replace(hour=10),
                ),
                "description": "Еженедельная встреча",
            },
            {
                "calendar": created_calendars[0],
                "title": "Презентация результатов",
                "start": datetime.combine(
                    today + timedelta(days=5),
                    datetime.min.time().replace(hour=14),
                ),
                "end": datetime.combine(
                    today + timedelta(days=5),
                    datetime.min.time().replace(hour=15, minute=30),
                ),
                "description": "Демо для заказчика",
            },
            # События для Анны (календарь 1 - личный)
            {
                "calendar": created_calendars[1],
                "title": "Врач",
                "start": datetime.combine(
                    today + timedelta(days=3),
                    datetime.min.time().replace(hour=16),
                ),
                "end": datetime.combine(
                    today + timedelta(days=3),
                    datetime.min.time().replace(hour=17),
                ),
                "description": "Плановый осмотр",
            },
            {
                "calendar": created_calendars[1],
                "title": "Фитнес",
                "start": datetime.combine(
                    today + timedelta(days=4),
                    datetime.min.time().replace(hour=19),
                ),
                "end": datetime.combine(
                    today + timedelta(days=4),
                    datetime.min.time().replace(hour=20),
                ),
                "description": "Тренировка",
            },
            # События для Петра (календарь 2 - проекты)
            {
                "calendar": created_calendars[2],
                "title": "Разработка нового модуля",
                "start": datetime.combine(
                    today, datetime.min.time().replace(hour=10)
                ),
                "end": datetime.combine(
                    today, datetime.min.time().replace(hour=18)
                ),
                "description": "Работа над функционалом",
            },
            {
                "calendar": created_calendars[2],
                "title": "Code Review",
                "start": datetime.combine(
                    today + timedelta(days=1),
                    datetime.min.time().replace(hour=15),
                ),
                "end": datetime.combine(
                    today + timedelta(days=1),
                    datetime.min.time().replace(hour=16),
                ),
                "description": "Проверка кода коллег",
            },
            # События для Петра (календарь 3 - встречи)
            {
                "calendar": created_calendars[3],
                "title": "Встреча с HR",
                "start": datetime.combine(
                    today + timedelta(days=2),
                    datetime.min.time().replace(hour=11),
                ),
                "end": datetime.combine(
                    today + timedelta(days=2),
                    datetime.min.time().replace(hour=12),
                ),
                "description": "Собеседование кандидата",
            },
            {
                "calendar": created_calendars[3],
                "title": "1-on-1 с руководителем",
                "start": datetime.combine(
                    today + timedelta(days=7),
                    datetime.min.time().replace(hour=14),
                ),
                "end": datetime.combine(
                    today + timedelta(days=7),
                    datetime.min.time().replace(hour=15),
                ),
                "description": "Обсуждение целей",
            },
            # События для Марии (календарь 4)
            {
                "calendar": created_calendars[4],
                "title": "Обучение новых сотрудников",
                "start": datetime.combine(
                    today + timedelta(days=1),
                    datetime.min.time().replace(hour=13),
                ),
                "end": datetime.combine(
                    today + timedelta(days=1),
                    datetime.min.time().replace(hour=16),
                ),
                "description": "Вводный курс",
            },
            {
                "calendar": created_calendars[4],
                "title": "Подготовка отчета",
                "start": datetime.combine(
                    today + timedelta(days=6),
                    datetime.min.time().replace(hour=10),
                ),
                "end": datetime.combine(
                    today + timedelta(days=6),
                    datetime.min.time().replace(hour=13),
                ),
                "description": "Квартальный отчет",
            },
        ]

        self.stdout.write("\nСоздание событий...")
        for event_data in events_data:
            start = (
                timezone.make_aware(event_data["start"])
                if timezone.is_naive(event_data["start"])
                else event_data["start"]
            )
            end = (
                timezone.make_aware(event_data["end"])
                if timezone.is_naive(event_data["end"])
                else event_data["end"]
            )

            event, created = Event.objects.get_or_create(
                calendar=event_data["calendar"],
                title=event_data["title"],
                start=start,
                defaults={
                    "end": end,
                    "description": event_data.get("description", ""),
                },
            )
            if created:
                self.stdout.write(
                    f"  Событие: {event.title} ({event.calendar.name})"
                )

        self.stdout.write("\n" + "=" * 60)
        self.stdout.write(self.style.SUCCESS("Готово! Создано:"))
        self.stdout.write(f"   Пользователи: {len(created_users)}")
        self.stdout.write(f"   Календари: {len(created_calendars)}")
        self.stdout.write(f"   События: {len(events_data)}")
        self.stdout.write("=" * 60)
        self.stdout.write("\nУчетные данные для входа:")
        for user_data in test_users:
            self.stdout.write(
                f"   {user_data['username']} / {user_data['password']}"
            )
        self.stdout.write("\n")
