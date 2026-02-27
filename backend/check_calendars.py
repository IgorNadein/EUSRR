from schedule.models import Calendar, Event

print("\n=== КАЛЕНДАРИ В БД ===")
calendars = Calendar.objects.all()
print(f"Всего календарей: {calendars.count()}")
for cal in calendars:
    events_count = Event.objects.filter(calendar=cal).count()
    print(f"  - ID: {cal.id}, Name: {cal.name}, Slug: {cal.slug}, События: {events_count}")

print("\n=== СОБЫТИЯ В БД ===")
events = Event.objects.all()
print(f"Всего событий: {events.count()}")
for event in events[:10]:  # Показываем первые 10
    print(f"  - ID: {event.id}, Title: {event.title}, Start: {event.start}, Calendar: {event.calendar.name if event.calendar else 'None'}")
if events.count() > 10:
    print(f"  ... и ещё {events.count() - 10} событий")
