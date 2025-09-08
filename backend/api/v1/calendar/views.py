# backend/api/v1/calendar/viewsets.py
from __future__ import annotations

import copy
import datetime as dt
from typing import List

from django.core.cache import cache
from django.db.models import Q
from django.db.models.functions import ExtractDay, ExtractMonth
from django.http import Http404
from django.utils.http import http_date, parse_http_date_safe
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.renderers import JSONRenderer
from rest_framework.response import Response
from rest_framework.viewsets import ViewSet

from calendar_app.models import CompanyEvent, DepartmentEvent, Recurrence
from .serializers import CompanyEventSerializer, DepartmentEventSerializer
from .utils import (
    CACHE_TTL,
    MAX_WINDOW_DAYS,
    RESPONSE_HEADERS,
    can_view_department,
    etag_for,
    get_range,
    last_modified,
)


class CompanyEventsViewSet(ViewSet):
    """
    GET /api/v1/calendar/company-events/?start=YYYY-MM-DD&end=YYYY-MM-DD
    Разворачивает ежегодные события в вхождения внутри окна.
    """

    permission_classes = [IsAuthenticated]
    renderer_classes = [JSONRenderer]

    def list(self, request):
        start, end = get_range(request)
        base_qs = CompanyEvent.objects.only(
            "id",
            "title",
            "description",
            "date",
            "recurrence",
            "color",
            "location",
            "created_at",
        )
        lm = last_modified(base_qs, CompanyEvent)

        # Без окна — просто всё (ограничим на всякий случай)
        if not (start and end):
            data = CompanyEventSerializer(
                base_qs.order_by("date")[:1000], many=True
            ).data
            resp = Response(data)
            for k, v in RESPONSE_HEADERS.items():
                resp.headers[k] = v
            return resp

        cache_key = (
            f"cal:v1:company:{request.user.id}:{start.isoformat()}:{end.isoformat()}"
        )
        cached = cache.get(cache_key)
        if cached:
            # ETag
            if request.META.get("HTTP_IF_NONE_MATCH") == cached["etag"]:
                return Response(status=304)
            # If-Modified-Since
            ims = request.META.get("HTTP_IF_MODIFIED_SINCE")
            if ims and lm:
                ims_ts = parse_http_date_safe(ims)
                if ims_ts:
                    ims_dt = dt.datetime.utcfromtimestamp(ims_ts).astimezone(
                        dt.timezone.utc
                    )
                    if lm <= ims_dt:
                        return Response(status=304)
            resp = Response(cached["data"])
            for k, v in cached["headers"].items():
                resp.headers[k] = v
            return resp

        # Фильтрация кандидатов: one-time в диапазоне + annual по (month, day)
        qs = CompanyEvent.objects.only(
            "id", "title", "description", "date", "recurrence", "color", "location"
        )
        qs = qs.annotate(month=ExtractMonth("date"), day=ExtractDay("date"))

        sm, sd = start.month, start.day
        em, ed = end.month, end.day
        one_time_q = Q(recurrence=Recurrence.ONE_TIME, date__range=(start, end))
        if (sm, sd) <= (em, ed):
            ge_start = Q(month__gt=sm) | (Q(month=sm) & Q(day__gte=sd))
            le_end = Q(month__lt=em) | (Q(month=em) & Q(day__lte=ed))
            annual_q = Q(recurrence=Recurrence.ANNUAL) & ge_start & le_end
        else:
            ge_start = Q(month__gt=sm) | (Q(month=sm) & Q(day__gte=sd))
            le_end = Q(month__lt=em) | (Q(month=em) & Q(day__lte=ed))
            annual_q = Q(recurrence=Recurrence.ANNUAL) & (ge_start | le_end)

        queryset = qs.filter(one_time_q | annual_q)

        # Разворачиваем annual → occurrence’ы
        items: List[CompanyEvent] = []
        for ev in queryset:
            if ev.recurrence == Recurrence.ONE_TIME:
                inst = copy.copy(ev)
                inst.occurrence_date = ev.date
                items.append(inst)
            else:
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
        if len(items) > 2000:
            items = items[:2000]

        data = CompanyEventSerializer(items, many=True).data
        etag = etag_for(cache_key, lm, len(data))
        headers = {**RESPONSE_HEADERS}
        if lm:
            headers["Last-Modified"] = http_date(lm.timestamp())
        headers["ETag"] = etag

        cache.set(
            cache_key, {"data": data, "headers": headers, "etag": etag}, CACHE_TTL
        )
        resp = Response(data)
        for k, v in headers.items():
            resp.headers[k] = v
        return resp


class DepartmentEventsViewSet(ViewSet):
    """
    GET /api/v1/calendar/departments/<int:pk>/events/?start=...&end=...
    Доступ: HR / руководитель отдела / сотрудник отдела.
    Разворачивает annual c сохранением длительности.
    """
    permission_classes = [IsAuthenticated]
    renderer_classes = [JSONRenderer]

    def _dept_id(self) -> int:
        try:
            return int(self.kwargs["pk"])
        except Exception:
            raise Http404

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        dept_id = self._dept_id()
        if not can_view_department(request.user, dept_id):
            raise Http404("Нет доступа к календарю этого отдела.")

    def list(self, request, *args, **kwargs):
        start, end = get_range(request)
        dept_id = self._dept_id()

        base = (DepartmentEvent.objects
                .filter(department_id=dept_id)
                .select_related("department")
                .only("id","title","description","start_date","end_date",
                      "all_day","recurrence","color","location","department","created_at"))
        lm = last_modified(base, DepartmentEvent)

        if not (start and end):
            data = DepartmentEventSerializer(base.order_by("start_date")[:1000], many=True).data
            resp = Response(data)
            for k, v in RESPONSE_HEADERS.items(): resp.headers[k] = v
            return resp

        cache_key = f"cal:v1:dept:{dept_id}:{request.user.id}:{start.isoformat()}:{end.isoformat()}"
        cached = cache.get(cache_key)
        if cached:
            if request.META.get("HTTP_IF_NONE_MATCH") == cached["etag"]:
                return Response(status=304)
            ims = request.META.get("HTTP_IF_MODIFIED_SINCE")
            if ims and lm:
                ims_ts = parse_http_date_safe(ims)
                if ims_ts:
                    ims_dt = dt.datetime.utcfromtimestamp(ims_ts).astimezone(dt.timezone.utc)
                    if lm <= ims_dt:
                        return Response(status=304)
            resp = Response(cached["data"])
            for k, v in cached["headers"].items(): resp.headers[k] = v
            return resp

        # ONE_TIME: overlap
        one_time = base.filter(
            Q(recurrence=Recurrence.ONE_TIME) &
            (Q(end_date__isnull=True, start_date__range=(start, end)) |
             Q(end_date__isnull=False, end_date__gte=start, start_date__lte=end))
        ).order_by("start_date")

        # ANNUAL: разворачивание (с длительностью)
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
        if len(items) > 2000:
            items = items[:2000]

        data = DepartmentEventSerializer(items, many=True).data
        etag = etag_for(cache_key, lm, len(data))
        headers = {**RESPONSE_HEADERS}
        if lm: headers["Last-Modified"] = http_date(lm.timestamp())
        headers["ETag"] = etag

        cache.set(cache_key, {"data": data, "headers": headers, "etag": etag}, CACHE_TTL)
        resp = Response(data)
        for k, v in headers.items(): resp.headers[k] = v
        return resp