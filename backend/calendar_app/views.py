# backend/calendar_app/views.py
from __future__ import annotations
import copy, hashlib, datetime as dt
from typing import Tuple, List

from django.db.models import Q, Max
from django.db.models.functions import ExtractDay, ExtractMonth
from django.http import Http404
from django.utils.dateparse import parse_date, parse_datetime
from django.utils.http import http_date, parse_http_date_safe
from django.utils import timezone
from django.core.cache import cache

from rest_framework import generics
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.renderers import JSONRenderer

from .models import CompanyEvent, DepartmentEvent, Recurrence
from .serializers import CompanyEventSerializer, DepartmentEventSerializer

# ---- Тюнинги ----
MAX_WINDOW_DAYS = 400
MAX_OCCURRENCES = 2000
CACHE_TTL = 60
RESPONSE_HEADERS = {"Cache-Control": f"private, max-age={CACHE_TTL}"}


def _parse_to_date(value: str | None) -> dt.date | None:
    if not value:
        return None
    dtime = parse_datetime(value)
    return dtime.date() if dtime else parse_date(value)


def _get_range(request) -> Tuple[dt.date | None, dt.date | None]:
    s = request.query_params.get("start") or request.query_params.get("from")
    e = request.query_params.get("end")   or request.query_params.get("to")
    if not (s and e):
        return None, None
    start = _parse_to_date(s); end = _parse_to_date(e)
    if not (start and end):
        return None, None
    if end < start:
        start, end = end, start
    if (end - start).days > MAX_WINDOW_DAYS:
        end = start + dt.timedelta(days=MAX_WINDOW_DAYS)
    return start, end


def _etag_for(payload_key: str, last_modified: dt.datetime | None, count: int) -> str:
    ts = int(last_modified.timestamp()) if last_modified else 0
    return hashlib.sha1(f"{payload_key}:{ts}:{count}".encode()).hexdigest()


def _last_modified_for_model(qs, model):
    # корректно берём поле: updated_at если есть, иначе created_at
    fields = {f.name for f in model._meta.get_fields() if hasattr(f, "name")}
    lm_field = "updated_at" if "updated_at" in fields else "created_at"
    return qs.aggregate(m=Max(lm_field)).get("m")


# ================= COMPANY =================

class CompanyEventListAPI(generics.ListAPIView):
    serializer_class = CompanyEventSerializer
    permission_classes = [IsAuthenticated]
    renderer_classes = [JSONRenderer]

    def _annual_qs_filtered(self, start: dt.date, end: dt.date):
        sm, sd = start.month, start.day
        em, ed = end.month, end.day
        annual = CompanyEvent.objects.filter(recurrence=Recurrence.ANNUAL) \
                                     .annotate(month=ExtractMonth("date"), day=ExtractDay("date")) \
                                     .only("id","title","description","date","recurrence","color","location")
        if (sm, sd) <= (em, ed):
            ge_start = Q(month__gt=sm) | (Q(month=sm) & Q(day__gte=sd))
            le_end   = Q(month__lt=em) | (Q(month=em) & Q(day__lte=ed))
            return annual.filter(ge_start & le_end)
        else:
            ge_start = Q(month__gt=sm) | (Q(month=sm) & Q(day__gte=sd))
            le_end   = Q(month__lt=em) | (Q(month=em) & Q(day__lte=ed))
            return annual.filter(ge_start | le_end)

    def list(self, request, *args, **kwargs):
        start, end = _get_range(request)
        base_qs = CompanyEvent.objects.only("id","title","description","date","recurrence","color","location")

        # Без диапазона — просто отдадим (обычно FullCalendar всегда шлёт окно)
        if not (start and end):
            data = CompanyEventSerializer(base_qs.order_by("date")[:MAX_OCCURRENCES], many=True).data
            return Response(data, headers=RESPONSE_HEADERS)

        lm = _last_modified_for_model(base_qs, CompanyEvent)
        cache_key = f"cal:company:{request.user.id}:{start.isoformat()}:{end.isoformat()}"
        cached = cache.get(cache_key)
        if cached:
            # 304 по ETag/IMS
            inm = request.META.get("HTTP_IF_NONE_MATCH")
            if inm and inm == cached.get("etag"):
                return Response(status=304, headers={"ETag": inm, **RESPONSE_HEADERS})
            ims = request.META.get("HTTP_IF_MODIFIED_SINCE")
            if ims and lm:
                ims_ts = parse_http_date_safe(ims)
                if ims_ts:
                    ims_dt = dt.datetime.utcfromtimestamp(ims_ts).replace(tzinfo=timezone.utc)
                    if lm <= ims_dt:
                        h = {"Last-Modified": http_date(lm.timestamp()), **RESPONSE_HEADERS}
                        return Response(status=304, headers=h)
            return Response(cached["data"], headers=cached["headers"])

        # ONE_TIME в окне
        one_time = base_qs.filter(recurrence=Recurrence.ONE_TIME, date__range=(start, end))
        # ANNUAL по (month, day)
        annual = self._annual_qs_filtered(start, end)

        # Разворачиваем
        items: List[CompanyEvent] = []
        for ev in one_time:
            inst = copy.copy(ev)
            inst.occurrence_date = ev.date
            items.append(inst)

        for ev in annual:
            for year in range(start.year, end.year + 1):
                try:
                    occ = ev.date.replace(year=year)
                except ValueError:
                    if ev.date.month == 2 and ev.date.day == 29:
                        occ = dt.date(year, 2, 28)
                    else:
                        continue
                if start <= occ <= end:
                    inst = copy.copy(ev)
                    inst.occurrence_date = occ
                    items.append(inst)

        items.sort(key=lambda o: getattr(o, "occurrence_date", o.date))
        if len(items) > MAX_OCCURRENCES:
            items = items[:MAX_OCCURRENCES]

        data = CompanyEventSerializer(items, many=True).data
        etag = _etag_for(cache_key, lm, len(data))
        headers = {**RESPONSE_HEADERS}
        if lm:
            headers["Last-Modified"] = http_date(lm.timestamp())
        headers["ETag"] = etag

        cache.set(cache_key, {"data": data, "headers": headers, "etag": etag}, CACHE_TTL)
        return Response(data, headers=headers)


# ================= DEPARTMENT =================

class DepartmentEventListAPI(generics.ListAPIView):
    serializer_class = DepartmentEventSerializer
    permission_classes = [IsAuthenticated]
    renderer_classes = [JSONRenderer]

    def _dept_id(self) -> int:
        try:
            return int(self.kwargs["pk"])
        except Exception:
            raise Http404

    def _check_access(self, user, dept_id: int) -> None:
        if user.is_active and (
            user.groups.filter(name="HR").exists()
            or user.has_perm("requests_app.can_view_all_requests")
            or user.has_perm("requests_app.can_process_requests")
            or user.headed_departments.filter(pk=dept_id).exists()
            or user.departments_links.filter(department_id=dept_id, is_active=True).exists()
        ):
            return
        raise Http404("Нет доступа к календарю этого отдела.")

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        self._check_access(request.user, self._dept_id())

    def list(self, request, *args, **kwargs):
        start, end = _get_range(request)
        dept_id = self._dept_id()

        base = (DepartmentEvent.objects
                .filter(department_id=dept_id)
                .select_related("department")
                .only("id","title","description","start_date","end_date",
                      "all_day","recurrence","color","location","department","created_at"))

        lm = _last_modified_for_model(base, DepartmentEvent)

        if not (start and end):
            data = DepartmentEventSerializer(base.order_by("start_date")[:MAX_OCCURRENCES], many=True).data
            return Response(data, headers=RESPONSE_HEADERS)

        cache_key = f"cal:dept:{dept_id}:{request.user.id}:{start.isoformat()}:{end.isoformat()}"
        cached = cache.get(cache_key)
        if cached:
            inm = request.META.get("HTTP_IF_NONE_MATCH")
            if inm and inm == cached.get("etag"):
                return Response(status=304, headers={"ETag": inm, **RESPONSE_HEADERS})
            ims = request.META.get("HTTP_IF_MODIFIED_SINCE")
            if ims and lm:
                ims_ts = parse_http_date_safe(ims)
                if ims_ts:
                    ims_dt = dt.datetime.utcfromtimestamp(ims_ts).replace(tzinfo=timezone.utc)
                    if lm <= ims_dt:
                        h = {"Last-Modified": http_date(lm.timestamp()), **RESPONSE_HEADERS}
                        return Response(status=304, headers=h)
            return Response(cached["data"], headers=cached["headers"])

        # ONE_TIME overlap
        one_time = base.filter(
            Q(recurrence=Recurrence.ONE_TIME) &
            (Q(end_date__isnull=True, start_date__range=(start, end)) |
             Q(end_date__isnull=False, end_date__gte=start, start_date__lte=end))
        ).order_by("start_date")

        # ANNUAL expand
        annual = base.filter(recurrence=Recurrence.ANNUAL)

        items: List[DepartmentEvent] = []

        for ev in one_time:
            obj = copy.copy(ev)
            obj.occ_start_date = ev.start_date
            obj.occ_end_date   = ev.end_date or ev.start_date
            items.append(obj)

        for ev in annual:
            s = ev.start_date; e = ev.end_date or ev.start_date
            dur = (e - s).days
            for year in range(start.year, end.year + 1):
                try:
                    s_y = s.replace(year=year)
                except ValueError:
                    if s.month == 2 and s.day == 29:
                        s_y = dt.date(year, 2, 28)
                    else:
                        continue
                e_y = s_y + dt.timedelta(days=dur)
                if not (e_y < start or s_y > end):
                    obj = copy.copy(ev)
                    obj.occ_start_date = s_y
                    obj.occ_end_date   = e_y
                    items.append(obj)

        items.sort(key=lambda o: getattr(o, "occ_start_date", o.start_date))
        if len(items) > MAX_OCCURRENCES:
            items = items[:MAX_OCCURRENCES]

        data = DepartmentEventSerializer(items, many=True).data
        etag = _etag_for(cache_key, lm, len(data))
        headers = {**RESPONSE_HEADERS}
        if lm:
            headers["Last-Modified"] = http_date(lm.timestamp())
        headers["ETag"] = etag

        cache.set(cache_key, {"data": data, "headers": headers, "etag": etag}, CACHE_TTL)
        return Response(data, headers=headers)
