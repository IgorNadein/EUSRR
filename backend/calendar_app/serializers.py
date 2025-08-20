# backend/calendar_app/serializers.py
import datetime as dt

from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime
from rest_framework import serializers

from .models import CompanyEvent, DepartmentEvent, Recurrence


def _aware(dt_or_date: dt.datetime | dt.date, to_utc: bool = False) -> dt.datetime:
    """
    Делает datetime aware в текущем TZ (или переводит в UTC).
    Если пришла date — берём локальную полночь.
    """
    if isinstance(dt_or_date, dt.date) and not isinstance(dt_or_date, dt.datetime):
        dtime = dt.datetime.combine(dt_or_date, dt.time.min)
    else:
        dtime = dt_or_date  # type: ignore[assignment]

    if timezone.is_naive(dtime):
        dtime = timezone.make_aware(dtime, timezone.get_current_timezone())

    if to_utc:
        dtime = timezone.localtime(dtime, timezone.utc)
    return dtime


def _as_iso(value, *, all_day: bool = True, to_utc: bool = False) -> str | None:
    """
    Приводит value (date | datetime | str | None) к ISO-строке.
    - Для all-day отдаём YYYY-MM-DD (без времени — так рекомендует FullCalendar).
    - Для timed делаем aware datetime (локальный TZ по умолчанию или UTC).
    """
    if value is None:
        return None

    # datetime
    if isinstance(value, dt.datetime):
        dtime = _aware(value, to_utc=to_utc)
        return dtime.isoformat()

    # date
    if isinstance(value, dt.date):
        if all_day:
            return value.isoformat()
        return _aware(value, to_utc=to_utc).isoformat()

    # str
    if isinstance(value, str):
        dtime = parse_datetime(value)
        if dtime:
            return _aware(dtime, to_utc=to_utc).isoformat()
        d = parse_date(value)
        if d:
            return d.isoformat() if all_day else _aware(d, to_utc=to_utc).isoformat()
        return value  # оставим как есть, чтобы не ронять API

    return None


class CompanyEventSerializer(serializers.ModelSerializer):
    start = serializers.SerializerMethodField()
    end = serializers.SerializerMethodField()
    allDay = serializers.SerializerMethodField()
    url = serializers.SerializerMethodField()
    recurrence_display = serializers.SerializerMethodField()

    class Meta:
        model = CompanyEvent
        fields = (
            "id",
            "title",
            "description",
            "start",
            "end",
            "allDay",
            "color",
            "location",
            "recurrence",
            "recurrence_display",
            "url",
        )
        read_only_fields = fields

    def get_start(self, obj: CompanyEvent):
        # Однодневное корпоративное событие
        occ = getattr(obj, "occurrence_date", None)
        return _as_iso(occ or obj.date, all_day=True)
    
    def get_end(self, obj: CompanyEvent):
        # Для all-day можно вернуть None (FullCalendar корректно отобразит один день)
        return None

    def get_allDay(self, obj: CompanyEvent):
        return True

    def get_url(self, obj: CompanyEvent):
        # Если детальной страницы нет — можно вернуть календарь компании
        try:
            return obj.get_absolute_url()
        except Exception:
            return None

    def get_recurrence_display(self, obj: CompanyEvent):
        return obj.get_recurrence_display()


class DepartmentEventSerializer(serializers.ModelSerializer):
    start = serializers.SerializerMethodField()
    end = serializers.SerializerMethodField()
    allDay = serializers.SerializerMethodField()
    url = serializers.SerializerMethodField()
    recurrence_display = serializers.SerializerMethodField()
    department_name = serializers.SerializerMethodField()

    class Meta:
        model = DepartmentEvent
        fields = (
            "id",
            "title",
            "description",
            "start",
            "end",
            "allDay",
            "color",
            "location",
            "recurrence",
            "recurrence_display",
            "department",  # id отдела
            "department_name",
            "url",
        )
        read_only_fields = fields

    def get_start(self, obj):
        start = getattr(obj, "occ_start_date", obj.start_date)
        return _as_iso(start, all_day=obj.all_day)

    def get_end(self, obj):
        end = getattr(obj, "occ_end_date", obj.end_date)
        if not end:
            return None
        if obj.all_day:
            # end-exclusive для all-day
            return _as_iso(end + dt.timedelta(days=1), all_day=True)
        return _as_iso(end, all_day=False)

    def get_allDay(self, obj: DepartmentEvent):
        return bool(obj.all_day)

    def get_url(self, obj: DepartmentEvent):
        try:
            return obj.get_absolute_url()
        except Exception:
            return None

    def get_recurrence_display(self, obj: DepartmentEvent):
        return obj.get_recurrence_display()

    def get_department_name(self, obj: DepartmentEvent):
        # избежим N+1: в view делайте select_related("department")
        dept = getattr(obj, "department", None)
        return getattr(dept, "name", None)
