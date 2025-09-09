from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import List, Optional, Union

from calendar_app.models import CalendarEvent, Recurrence


@dataclass
class Occurrence:
    """Материализованное вхождение события.

    Attributes:
        start (datetime|date): Начало вхождения.
        end (datetime|date): Конец вхождения (для дат — конец дня, для datetime — точный момент).
        all_day (bool): Признак события на весь день.

    Optional Meta (можно не задавать при создании):
        id (int|None)
        title (str|None)
        color (str|None)
        recurrence (str|None)
        department_id (int|None)
    """
    start: Union[datetime, date]
    end: Union[datetime, date]
    all_day: bool

    id: Optional[int] = None
    title: Optional[str] = None
    color: Optional[str] = None
    recurrence: Optional[str] = None
    department_id: Optional[int] = None

    @property
    def allDay(self) -> bool:
        """Legacy-алиас для совместимости с camelCase."""
        return self.all_day


# ===== вспомогательные функции работы с датами/временем =====

def _clamp_day(year: int, month: int, day: int) -> date:
    """Безопасно подбирает день месяца (31→30→29→28)."""
    for d in (day, 30, 29, 28):
        try:
            return date(year, month, min(d, day))
        except ValueError:
            continue
    return date(year, month, 28)


def _add_months(d: date, months: int) -> date:
    y = d.year + (d.month - 1 + months) // 12
    m = (d.month - 1 + months) % 12 + 1
    return _clamp_day(y, m, d.day)


def _add_years(d: date, years: int) -> date:
    y = d.year + years
    m = d.month
    dd = d.day
    if m == 2 and dd == 29:
        try:
            return date(y, 2, 29)
        except ValueError:
            return date(y, 2, 28)
    return date(y, m, dd)


def _overlaps(a_start, a_end, b_start, b_end) -> bool:
    """Проверяет пересечение двух интервалов одинакового типа (оба date либо оба datetime)."""
    return a_start < b_end and a_end > b_start


# ===== основная функция развёртки =====

def expand_event_occurrences(
    ev: CalendarEvent,
    range_start: Union[date, datetime],
    range_end: Union[date, datetime],
    max_instances: int = 1000,
) -> List[Occurrence]:
    """Материализует вхождения события в окне [range_start, range_end).

    Args:
        ev: Экземпляр CalendarEvent.
        range_start: Левая граница окна (включительно), допускается date или datetime.
        range_end: Правая граница окна (исключительно), допускается date или datetime.
        max_instances: Жёсткий лимит количества вхождений (для безопасности).

    Returns:
        list[Occurrence]: Список вхождений.

    Notes:
        - Для all-day события используется сравнение по датам.
        - Для событий с временем — сравнение по datetime (окно приводится к datetime).
        - Минимальная длительность: 1 день для all-day, 1 минута для timed.
    """
    # пустое окно
    if isinstance(range_start, datetime) and isinstance(range_end, datetime):
        if range_start >= range_end:
            return []
    else:
        # приводим к датам для проверки, если хотя бы один — date
        rs_d = range_start.date() if isinstance(range_start, datetime) else range_start
        re_d = range_end.date() if isinstance(range_end, datetime) else range_end
        if rs_d >= re_d:
            return []

    all_day = ev.all_day
    s_date = ev.start_date
    e_date = ev.end_date or ev.start_date
    s_time: Optional[time] = ev.start_time
    e_time: Optional[time] = ev.end_time

    # базовые границы одного экземпляра
    base_start = datetime.combine(s_date, s_time or time.min) if not all_day else s_date
    base_end   = datetime.combine(e_date, e_time or time.max) if not all_day else e_date

    # длительность одного экземпляра
    duration = (
        (base_end - base_start)
        if not all_day
        else timedelta(days=(e_date - s_date).days + 1)
    )
    if duration <= timedelta(0):
        duration = timedelta(minutes=1) if not all_day else timedelta(days=1)

    # нормализуем окно под тип события (чтобы не сравнивать datetime с date)
    if all_day:
        RS = range_start.date() if isinstance(range_start, datetime) else range_start
        RE = range_end.date() if isinstance(range_end, datetime) else range_end

        def push(start_d: date) -> bool:
            end_d = start_d + duration  # timedelta дней
            if _overlaps(start_d, end_d, RS, RE):
                occ.append(Occurrence(start=start_d, end=end_d, all_day=True))
            return len(occ) >= max_instances
    else:
        RS = range_start if isinstance(range_start, datetime) else datetime.combine(range_start, time.min)
        RE = range_end if isinstance(range_end, datetime) else datetime.combine(range_end, time.min)

        def push(start_dt: datetime) -> bool:
            end_dt = start_dt + duration
            if _overlaps(start_dt, end_dt, RS, RE):
                occ.append(Occurrence(start=start_dt, end=end_dt, all_day=False))
            return len(occ) >= max_instances

    occ: List[Occurrence] = []

    rec = ev.recurrence
    interval = max(1, ev.recurrence_interval or 1)
    until: Optional[date] = ev.recurrence_until
    count_limit = ev.recurrence_count or 10**9
    produced = 0

    # ---- ONE-TIME
    if rec == Recurrence.ONE_TIME:
        push(base_start if not all_day else s_date)
        return occ

    # ---- HOURLY (только timed)
    if rec == Recurrence.HOURLY:
        # базовый курсор
        cur = datetime.combine(s_date, s_time or time.min)

        # догоняем до начала окна
        while cur + duration <= RS:
            cur += timedelta(hours=interval)

        # генерация в окне
        while produced < count_limit and (until is None or cur.date() <= until):
            if cur >= RE:
                break
            if push(cur):
                break
            produced += 1
            cur += timedelta(hours=interval)
        return occ

    # ---- DAILY
    if rec == Recurrence.DAILY:
        cur = s_date
        # догоняем до начала окна
        RS_d = RS if all_day else RS.date()
        while cur + timedelta(days=1) <= RS_d:
            cur += timedelta(days=interval)

        while produced < count_limit and (until is None or cur <= until):
            # выход за окно
            RE_d = RE if all_day else RE.date()
            if cur >= RE_d:
                break
            if push(cur if all_day else datetime.combine(cur, s_time or time.min)):
                break
            produced += 1
            cur += timedelta(days=interval)
        return occ

    # ---- WEEKLY
    if rec == Recurrence.WEEKLY:
        mask = ev.weekdays_mask or 0
        allowed = {i for i in range(7) if (mask >> i) & 1} or {s_date.weekday()}

        def weeks_from_start(d: date) -> int:
            return (d - s_date).days // 7

        cur = max(s_date, RS if isinstance(RS, date) else RS.date())
        safe_guard = 0
        while produced < count_limit and cur < (RE if isinstance(RE, date) else RE.date()) and safe_guard < max_instances * 14:
            if (weeks_from_start(cur) % interval == 0) and (cur.weekday() in allowed):
                if push(cur if all_day else datetime.combine(cur, s_time or time.min)):
                    break
                produced += 1
            cur += timedelta(days=1)
            if until and cur > until:
                break
            safe_guard += 1
        return occ

    # ---- MONTHLY
    if rec == Recurrence.MONTHLY:
        cur = s_date
        RS_d = RS if all_day else RS.date()
        while _add_months(cur, interval) <= RS_d:
            cur = _add_months(cur, interval)

        while produced < count_limit and (until is None or cur <= until):
            RE_d = RE if all_day else RE.date()
            if cur >= RE_d:
                break
            if push(cur if all_day else datetime.combine(cur, s_time or time.min)):
                break
            produced += 1
            cur = _add_months(cur, interval)
        return occ

    # ---- ANNUAL
    if rec == Recurrence.ANNUAL:
        cur = s_date
        RS_d = RS if all_day else RS.date()
        nxt = _add_years(cur, interval)
        while nxt <= RS_d:
            cur = nxt
            nxt = _add_years(cur, interval)

        while produced < count_limit and (until is None or cur <= until):
            RE_d = RE if all_day else RE.date()
            if cur >= RE_d:
                break
            if push(cur if all_day else datetime.combine(cur, s_time or time.min)):
                break
            produced += 1
            cur = _add_years(cur, interval)
        return occ

    # fallback
    push(base_start if not all_day else s_date)
    return occ
