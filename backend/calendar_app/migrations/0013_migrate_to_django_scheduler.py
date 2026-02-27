# Generated migration for calendar_app → schedule data migration

from django.db import migrations
from django.utils import timezone
from django.utils.text import slugify
from datetime import datetime, time


def migrate_to_django_scheduler(apps, schema_editor):
    """
    Мигрирует данные из calendar_app в django-scheduler.
    
    Создает:
    - Системные календари (компания, отделы, личные)
    - Мигрирует пользовательские календари
    - Мигрирует события с конвертацией повторяемости
    - Мигрирует подписки в CalendarRelation
    """
    # ВАЖНО: Получаем ContentType через apps.get_model для миграций!
    ContentType = apps.get_model('contenttypes', 'ContentType')
    
    # Old models
    OldCalendar = apps.get_model('calendar_app', 'Calendar')
    OldCalendarEvent = apps.get_model('calendar_app', 'CalendarEvent')
    OldCalendarSubscription = apps.get_model('calendar_app', 'CalendarSubscription')
    
    # New models (django-scheduler)
    NewCalendar = apps.get_model('schedule', 'Calendar')
    NewEvent = apps.get_model('schedule', 'Event')
    NewRule = apps.get_model('schedule', 'Rule')
    CalendarRelation = apps.get_model('schedule', 'CalendarRelation')
    
    # Employee & Department
    Employee = apps.get_model('employees', 'Employee')
    Department = apps.get_model('employees', 'Department')
    
    employee_ct = ContentType.objects.get_for_model(Employee)
    
    print("\n" + "="*80)
    print("НАЧАЛО МИГРАЦИИ: calendar_app → django-scheduler")
    print("="*80 + "\n")
    
    # ===== ШАГ 1: Создание системных календарей =====
    print("ШАГ 1: Создание системных календарей...")
    print("-" * 80)
    
    # 1.1. Глобальный календарь компании
    company_cal, created = NewCalendar.objects.get_or_create(
        slug='company-global',
        defaults={'name': '🏢 Календарь компании'}
    )
    if created:
        print(f"  ✅ Создан: {company_cal.name}")
    else:
        print(f"  ℹ️  Уже существует: {company_cal.name}")
    
    # Все сотрудники как viewers для глобального календаря
    for emp in Employee.objects.filter(is_active=True):
        try:
            CalendarRelation.objects.create(
                calendar=company_cal,
                content_type=employee_ct,
                object_id=emp.id,
                distinction='viewer',
                inheritable=True
            )
        except Exception:
            # Уже существует, пропускаем
            pass
    
    # 1.2. Календари отделов
    dept_calendars = {}
    departments = Department.objects.all()
    print(f"\n  Создание календарей отделов ({departments.count()})...")
    
    for dept in departments:
        slug = f'dept-{dept.id}'
        cal, created = NewCalendar.objects.get_or_create(
            slug=slug,
            defaults={'name': f'🏛️ {dept.name}'}
        )
        dept_calendars[dept.id] = cal
        
        if created:
            print(f"    ✅ {cal.name}")
        
        # Руководитель отдела как owner
        if hasattr(dept, 'head') and dept.head:
            try:
                CalendarRelation.objects.create(
                    calendar=cal,
                    content_type=employee_ct,
                    object_id=dept.head.id,
                    distinction='owner',
                    inheritable=True
                )
            except Exception:
                pass
        
        # Члены отдела как viewers
        # Получаем через обратную связь EmployeeDepartment
        EmployeeDepartment = apps.get_model('employees', 'EmployeeDepartment')
        dept_links = EmployeeDepartment.objects.filter(department=dept, is_active=True).select_related('employee')
        for link in dept_links:
            if link.employee:
                try:
                    CalendarRelation.objects.create(
                        calendar=cal,
                        content_type=employee_ct,
                        object_id=link.employee.id,
                        distinction='viewer',
                        inheritable=True
                    )
                except Exception:
                    pass
    
    print(f"  ✅ Создано {len(dept_calendars)} календарей отделов")
    
    # 1.3. Личные календари пользователей
    personal_calendars = {}
    employees = Employee.objects.filter(is_active=True)
    print(f"\n  Создание личных календарей ({employees.count()})...")
    
    for emp in employees:
        slug = f'personal-{emp.id}'
        cal, created = NewCalendar.objects.get_or_create(
            slug=slug,
            defaults={'name': '👤 Мой календарь'}
        )
        personal_calendars[emp.id] = cal
        
        # Владелец
        try:
            CalendarRelation.objects.create(
                calendar=cal,
                content_type=employee_ct,
                object_id=emp.id,
                distinction='owner',
                inheritable=True
            )
        except Exception:
            pass
    
    print(f"  ✅ Создано {len(personal_calendars)} личных календарей")
    
    total_system_cals = 1 + len(dept_calendars) + len(personal_calendars)
    print(f"\n✅ Всего создано системных календарей: {total_system_cals}\n")
    
    # ===== ШАГ 2: Миграция пользовательских календарей =====
    print("ШАГ 2: Миграция пользовательских календарей...")
    print("-" * 80)
    
    calendar_mapping = {}  # old_calendar.id → new_calendar
    old_calendars = OldCalendar.objects.all()
    
    for old_cal in old_calendars:
        # Генерируем уникальный slug
        base_slug = slugify(old_cal.title) or f'calendar-{old_cal.id}'
        slug = f'legacy-{base_slug}'
        
        # Проверяем уникальность
        counter = 1
        final_slug = slug
        while NewCalendar.objects.filter(slug=final_slug).exists():
            final_slug = f'{slug}-{counter}'
            counter += 1
        
        new_cal = NewCalendar.objects.create(
            name=old_cal.title,
            slug=final_slug
        )
        calendar_mapping[old_cal.id] = new_cal
        
        # Создаем CalendarRelation для владельца
        if old_cal.owner_user_id:
            try:
                CalendarRelation.objects.create(
                    calendar=new_cal,
                    content_type=employee_ct,
                    object_id=old_cal.owner_user_id,
                    distinction='owner',
                    inheritable=True
                )
            except Exception:
                pass
        elif old_cal.owner_department_id:
            # Владелец отдела = руководитель
            dept = Department.objects.filter(id=old_cal.owner_department_id).first()
            if dept and hasattr(dept, 'head') and dept.head:
                try:
                    CalendarRelation.objects.create(
                        calendar=new_cal,
                        content_type=employee_ct,
                        object_id=dept.head.id,
                        distinction='owner',
                        inheritable=True
                    )
                except Exception:
                    pass
        
        print(f"  ✅ {old_cal.title} → {final_slug}")
    
    print(f"\n✅ Мигрировано {len(calendar_mapping)} пользовательских календарей\n")
    
    # ===== ШАГ 3: Миграция событий =====
    print("ШАГ 3: Миграция событий...")
    print("-" * 80)
    
    old_events = OldCalendarEvent.objects.all()
    migrated_count = 0
    skipped_count = 0
    
    print(f"  Всего событий для миграции: {old_events.count()}\n")
    
    for old_event in old_events:
        try:
            # Пропускаем старые события дней рождения - они будут созданы заново в ШАГе 5
            if hasattr(old_event, 'source') and old_event.source and old_event.source.endswith(':birthday'):
                skipped_count += 1
                continue
            
            # Определяем целевой календарь
            target_cal = None
            
            if old_event.calendar_id:
                # Событие в пользовательском календаре
                target_cal = calendar_mapping.get(old_event.calendar_id)
            elif old_event.employee_id:
                # Личное событие
                target_cal = personal_calendars.get(old_event.employee_id)
            elif old_event.department_id:
                # Событие отдела
                target_cal = dept_calendars.get(old_event.department_id)
            else:
                # Глобальное событие компании
                target_cal = company_cal
            
            if not target_cal:
                print(f"  ⚠️  Пропущено (нет календаря): {old_event.title}")
                skipped_count += 1
                continue
            
            # Конвертация даты+время → datetime
            if old_event.all_day:
                start_dt = timezone.make_aware(
                    datetime.combine(old_event.start_date, time(0, 0))
                )
                end_date = old_event.end_date or old_event.start_date
                end_dt = timezone.make_aware(
                    datetime.combine(end_date, time(23, 59, 59))
                )
            else:
                start_time = old_event.start_time or time(0, 0)
                start_dt = timezone.make_aware(
                    datetime.combine(old_event.start_date, start_time)
                )
                
                end_date = old_event.end_date or old_event.start_date
                end_time = old_event.end_time or start_time
                end_dt = timezone.make_aware(
                    datetime.combine(end_date, end_time)
                )
            
            # Создаем Rule если есть повторяемость
            rule = None
            end_recurring_period = None
            
            if old_event.recurrence != 'one_time':
                rule = create_rule_from_recurrence(
                    NewRule,
                    old_event.recurrence,
                    old_event.recurrence_interval,
                    old_event.weekdays_mask,
                    old_event.recurrence_until,
                    old_event.recurrence_count,
                    old_event.title
                )
                
                if old_event.recurrence_until:
                    end_recurring_period = timezone.make_aware(
                        datetime.combine(old_event.recurrence_until, time(23, 59, 59))
                    )
            
            # Создаем новое событие
            new_event = NewEvent.objects.create(
                calendar=target_cal,
                title=old_event.title,
                description=old_event.description or '',
                start=start_dt,
                end=end_dt,
                rule=rule,
                end_recurring_period=end_recurring_period,
                color_event=old_event.color if old_event.color else None,
            )
            
            migrated_count += 1
            
            # Прогресс каждые 50 событий
            if migrated_count % 50 == 0:
                print(f"  ... обработано {migrated_count} событий")
        
        except Exception as e:
            print(f"  ❌ Ошибка миграции '{old_event.title}': {e}")
            skipped_count += 1
            continue
    
    print(f"\n✅ Мигрировано событий: {migrated_count}")
    if skipped_count > 0:
        print(f"⚠️  Пропущено событий: {skipped_count}")
    print()
    
    # ===== ШАГ 4: Миграция подписок =====
    print("ШАГ 4: Миграция подписок...")
    print("-" * 80)
    
    subscriptions = OldCalendarSubscription.objects.all()
    migrated_subs = 0
    
    for sub in subscriptions:
        target_cal = calendar_mapping.get(sub.calendar_id)
        if not target_cal:
            continue
        
        # Определяем distinction из прав
        if sub.can_manage:
            distinction = 'owner'
        elif sub.can_edit:
            distinction = 'editor'
        else:
            distinction = 'viewer'
        
        try:
            CalendarRelation.objects.create(
                calendar=target_cal,
                content_type=employee_ct,
                object_id=sub.user_id,
                distinction=distinction,
                inheritable=True
            )
        except Exception:
            pass
        migrated_subs += 1
    
    print(f"✅ Мигрировано подписок: {migrated_subs}\n")
    
    # ===== ШАГ 5: Синхронизация дней рождения =====
    print("ШАГ 5: Синхронизация дней рождения...")
    print("-" * 80)
    
    employees_with_birthdays = Employee.objects.filter(
        birth_date__isnull=False,
        is_active=True
    )
    print(f"  Сотрудников с датой рождения: {employees_with_birthdays.count()}\n")
    
    birthday_created = 0
    birthday_skipped = 0
    
    # Получаем или создаем правило для ежегодного повторения
    yearly_rule, _ = NewRule.objects.get_or_create(
        name='Ежегодно',
        defaults={
            'description': 'Повторять каждый год',
            'frequency': 'YEARLY',
            'params': ''
        }
    )
    
    for emp in employees_with_birthdays:
        try:
            # Получаем личный календарь (уже создан в Шаге 1.3)
            personal_cal = personal_calendars.get(emp.id)
            if not personal_cal:
                birthday_skipped += 1
                continue
            
            # Создаем событие дня рождения
            full_name = f"{emp.last_name} {emp.first_name}" if emp.last_name and emp.first_name else f"Employee #{emp.id}"
            title = f"🎂 День рождения: {full_name}"
            
            # Вычисляем даты для текущего года
            current_year = timezone.now().year
            start_dt = timezone.make_aware(
                datetime(current_year, emp.birth_date.month, emp.birth_date.day, 0, 0)
            )
            end_dt = start_dt + timezone.timedelta(days=1)
            
            NewEvent.objects.create(
                title=title,
                start=start_dt,
                end=end_dt,
                calendar=personal_cal,
                creator_id=emp.id,
                rule=yearly_rule,
                end_recurring_period=None,  # Бесконечное повторение
                color_event='#FFC107',  # Жёлтый/золотой цвет
                description=f"Автоматическое событие: день рождения {full_name}"
            )
            birthday_created += 1
            
            # Прогресс каждые 20 событий
            if birthday_created % 20 == 0:
                print(f"  ... создано {birthday_created} событий дней рождения")
        
        except Exception as e:
            print(f"  ⚠️  Ошибка для {emp}: {e}")
            birthday_skipped += 1
    
    print(f"\n✅ Создано событий дней рождения: {birthday_created}")
    if birthday_skipped > 0:
        print(f"⚠️  Пропущено: {birthday_skipped}")
    print()
    
    # ===== ИТОГИ =====
    print("="*80)
    print("МИГРАЦИЯ ЗАВЕРШЕНА УСПЕШНО ✅")
    print("="*80)
    print(f"\n📊 Статистика:")
    print(f"  • Системных календарей: {total_system_cals}")
    print(f"  • Пользовательских календарей: {len(calendar_mapping)}")
    print(f"  • Событий: {migrated_count}")
    print(f"  • Подписок: {migrated_subs}")
    print(f"  • Дней рождения: {birthday_created}")
    print(f"\n⚠️  Примечания:")
    print(f"  • Старые данные calendar_app НЕ удалены (для возможности отката)")
    print(f"  • События дней рождения созданы автоматически для всех сотрудников")
    print(f"  • Потеряны: color_override, is_visible, notify_* из CalendarSubscription")
    print(f"  • Рекомендуется тестирование перед удалением старых таблиц")
    print()


def create_rule_from_recurrence(Rule, recurrence, interval, weekdays_mask, until, count, event_title):
    """
    Создает Rule из параметров повторяемости calendar_app.
    
    Args:
        Rule: Модель django-scheduler Rule
        recurrence: 'hourly'|'daily'|'weekly'|'monthly'|'annual'
        interval: Интервал повторения
        weekdays_mask: Битовая маска дней недели (1=Пн, 2=Вт, 4=Ср, 8=Чт, 16=Пт, 32=Сб, 64=Вс)
        until: Дата окончания повторений
        count: Количество повторений
        event_title: Название события (для имени Rule)
    
    Returns:
        Rule instance
    """
    # Маппинг частоты
    freq_mapping = {
        'hourly': 'HOURLY',
        'daily': 'DAILY',
        'weekly': 'WEEKLY',
        'monthly': 'MONTHLY',
        'annual': 'YEARLY',
    }
    
    frequency = freq_mapping.get(recurrence, 'DAILY')
    
    # Формирование params (RFC 5545 format)
    params_parts = []
    
    # Interval
    if interval and interval > 1:
        params_parts.append(f'interval:{interval}')
    
    # Weekdays (для weekly events)
    if recurrence == 'weekly' and weekdays_mask:
        days = []
        if weekdays_mask & 1: days.append('0')    # Пн
        if weekdays_mask & 2: days.append('1')    # Вт
        if weekdays_mask & 4: days.append('2')    # Ср
        if weekdays_mask & 8: days.append('3')    # Чт
        if weekdays_mask & 16: days.append('4')   # Пт
        if weekdays_mask & 32: days.append('5')   # Сб
        if weekdays_mask & 64: days.append('6')   # Вс
        
        if days:
            params_parts.append(f'byweekday:{",".join(days)}')
    
    # Until date
    if until:
        params_parts.append(f'until:{until.strftime("%Y%m%d")}')
    
    # Count
    if count:
        params_parts.append(f'count:{count}')
    
    params = ';'.join(params_parts) if params_parts else ''
    
    # Создаем Rule
    rule_name = f'{event_title[:25]} - {frequency}'
    rule_desc = f'Migrated from calendar_app: {recurrence} every {interval}'
    
    rule = Rule.objects.create(
        name=rule_name,
        description=rule_desc,
        frequency=frequency,
        params=params
    )
    
    return rule


def reverse_migration(apps, schema_editor):
    """
    Откат миграции: удаление мигрированных данных из django-scheduler.
    
    ⚠️ ВНИМАНИЕ: Это удалит ВСЕ календари и события из django-scheduler,
    созданные этой миграцией. Старые данные в calendar_app останутся.
    """
    NewCalendar = apps.get_model('schedule', 'Calendar')
    
    print("\n⚠️  ОТКАТ МИГРАЦИИ: Удаление мигрированных календарей...")
    
    # Удаляем по slug prefix
    deleted = 0
    
    # Системные календари
    count, _ = NewCalendar.objects.filter(slug='company-global').delete()
    deleted += count
    
    count, _ = NewCalendar.objects.filter(slug__startswith='dept-').delete()
    deleted += count
    
    count, _ = NewCalendar.objects.filter(slug__startswith='personal-').delete()
    deleted += count
    
    # Пользовательские календари
    count, _ = NewCalendar.objects.filter(slug__startswith='legacy-').delete()
    deleted += count
    
    print(f"✅ Удалено календарей: {deleted}")
    print("⚠️  Старые данные в calendar_app сохранены")


class Migration(migrations.Migration):
    
    dependencies = [
        ('calendar_app', '0012_alter_calendarsubscription_color_override'),
        ('schedule', '0015_rename_indexes'),  # django-scheduler last migration
        ('employees', '0001_initial'),  # Зависимость от Employee model
        ('contenttypes', '0002_remove_content_type_name'),  # Для CalendarRelation
    ]
    
    operations = [
        migrations.RunPython(
            migrate_to_django_scheduler,
            reverse_migration
        ),
    ]
