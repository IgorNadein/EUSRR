# calendar_app/views.py
from rest_framework import generics
from django.utils.dateparse import parse_datetime, parse_date
from django.db.models import Q
from .models import CompanyEvent
from .serializers import CompanyEventSerializer


class CompanyEventListAPI(generics.ListAPIView):
    serializer_class = CompanyEventSerializer

    def get_queryset(self):
        qs = CompanyEvent.objects.all()
        start_str = self.request.query_params.get('start')
        end_str = self.request.query_params.get('end')

        if start_str and end_str:
            # сначала пытаемся распарсить как datetime, иначе как date
            dt_start = parse_datetime(start_str) or parse_date(start_str)
            dt_end = parse_datetime(end_str) or parse_date(end_str)
            # если получилось datetime, приводим к date
            if hasattr(dt_start, 'date'):
                start = dt_start.date()
            else:
                start = dt_start
            if hasattr(dt_end, 'date'):
                end = dt_end.date()
            else:
                end = dt_end

            # если всё ещё нет корректных дат — вернём пустой qs
            if not start or not end:
                return CompanyEvent.objects.none()

            # 1) одноразовые события внутри диапазона
            one_time_q = Q(recurrence=CompanyEvent.ONE_TIME,
                           date__range=(start, end))

            # 2) ежегодные события, чья (month, day) лежит в интервале [start, end]
            annual_ids = []
            for ev in CompanyEvent.objects.filter(recurrence=CompanyEvent.ANNUAL):
                md = (ev.date.month, ev.date.day)
                # простой кейс: диапазон в рамках одного года
                if start.year == end.year:
                    if (start.month, start.day) <= md <= (end.month, end.day):
                        annual_ids.append(ev.pk)
                else:
                    # диапазон пересёк границу года
                    if md >= (start.month, start.day) or md <= (end.month, end.day):
                        annual_ids.append(ev.pk)
            annual_q = Q(pk__in=annual_ids)

            return qs.filter(one_time_q | annual_q)

        # если start/end не заданы — вернём всё
        return qs
