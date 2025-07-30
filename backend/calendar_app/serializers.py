# calendar_app/serializers.py
from rest_framework import serializers
from django.utils.dateparse import parse_datetime, parse_date
from .models import CompanyEvent


class CompanyEventSerializer(serializers.ModelSerializer):
    # переопределяем поле date
    date = serializers.SerializerMethodField()

    class Meta:
        model = CompanyEvent
        fields = ['id', 'title', 'date', 'recurrence']

    def get_date(self, obj):
        request = self.context.get('request')
        start_str = request.query_params.get('start')
        # парсим start, чтобы узнать год
        dt_start = parse_datetime(start_str) or parse_date(start_str)
        if hasattr(dt_start, 'date'):
            start = dt_start.date()
        else:
            start = dt_start
        # если это annual — заменяем год на нужный
        if obj.recurrence == CompanyEvent.ANNUAL and start:
            return obj.date.replace(year=start.year).isoformat()
        # иначе — отдаем оригинальную дату
        return obj.date.isoformat()
