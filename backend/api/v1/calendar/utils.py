# backend/api/v1/calendar/utils.py
from __future__ import annotations

import datetime as dt
import hashlib
from typing import Optional, Tuple

from django.db.models import Max, Q
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime

MAX_WINDOW_DAYS = 400
CACHE_TTL = 60
RESPONSE_HEADERS = {"Cache-Control": f"private, max-age={CACHE_TTL}"}


def parse_to_date(value: Optional[str]) -> Optional[dt.date]:
    if not value:
        return None
    dtime = parse_datetime(value)
    return dtime.date() if dtime else parse_date(value)


def get_range(request) -> Tuple[Optional[dt.date], Optional[dt.date]]:
    s = request.query_params.get("start") or request.query_params.get("from")
    e = request.query_params.get("end") or request.query_params.get("to")
    if not (s and e):
        return None, None
    start = parse_to_date(s)
    end = parse_to_date(e)
    if not (start and end):
        return None, None
    if end < start:
        start, end = end, start
    if (end - start).days > MAX_WINDOW_DAYS:
        end = start + dt.timedelta(days=MAX_WINDOW_DAYS)
    return start, end


def etag_for(payload_key: str, last_modified: Optional[dt.datetime], count: int) -> str:
    src = f"{payload_key}:{int(last_modified.timestamp()) if last_modified else 0}:{count}"
    return hashlib.sha1(src.encode()).hexdigest()


def last_modified(qs, model) -> Optional[dt.datetime]:
    field_names = {f.name for f in model._meta.get_fields() if hasattr(f, "name")}
    field = "updated_at" if "updated_at" in field_names else "created_at"
    return qs.aggregate(m=Max(field)).get("m")


def is_hr(user) -> bool:
    return user.is_active and (
        user.groups.filter(name="HR").exists()
        or user.has_perm("requests_app.can_view_all_requests")
        or user.has_perm("requests_app.can_process_requests")
    )


def can_view_department(user, dept_id: int) -> bool:
    if is_hr(user):
        return True
    if user.headed_departments.filter(pk=dept_id).exists():
        return True
    return user.departments_links.filter(department_id=dept_id, is_active=True).exists()