# backend/api/v1/calendar/serializers.py
from __future__ import annotations

import re
from datetime import date, datetime, time, timedelta
from typing import Any, Dict, List, Optional

from calendar_app.models import CalendarEvent, Recurrence
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers


class CalendarEventWriteSerializer(serializers.ModelSerializer):
    """Создание/обновление события календаря с полной валидацией."""

    # Разрешаем пустой список для PATCH (когда меняют weekly -> daily и присылают weekdays: [])
    weekdays = serializers.ListField(
        child=serializers.IntegerField(min_value=0, max_value=6),
        required=False,
        allow_empty=True,
        write_only=True,
        help_text="Список дней недели для WEEKLY (0=Mon..6=Sun).",
    )
    department_id = serializers.IntegerField(required=False, allow_null=True)
    employee_id = serializers.IntegerField(required=False, allow_null=True)

    class Meta:
        model = CalendarEvent
        fields = (
            "id",
            "department_id",
            "employee_id",
            "title",
            "description",
            "start_date",
            "end_date",
            "start_time",
            "end_time",
            "all_day",
            "recurrence",
            "recurrence_interval",
            "recurrence_until",
            "recurrence_count",
            "weekdays_mask",
            "weekdays",  # write-only
            "color",
            "location",
        )
        read_only_fields = ("id",)

    # ---- helpers
    def _coalesce(self, data: Dict[str, Any], instance: Optional[CalendarEvent], key: str, default=None):
        if key in data:
            return data.get(key)
        if instance is not None:
            return getattr(instance, key)
        return default

    @staticmethod
    def _weekdays_to_mask(values: list[int]) -> int:
        mask = 0
        for v in values:
            iv = int(v)
            if not (0 <= iv <= 6):
                raise ValueError("weekday out of range")
            mask |= (1 << iv)
        return mask

    # ---- validation
    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        inst: Optional[CalendarEvent] = getattr(self, "instance", None)
        is_create = inst is None

        s_date: date = self._coalesce(attrs, inst, "start_date")
        if not s_date:
            raise serializers.ValidationError({"start_date": _("Обязательное поле.")})

        e_date: Optional[date] = self._coalesce(attrs, inst, "end_date", None)
        s_time: Optional[time] = self._coalesce(attrs, inst, "start_time", None)
        e_time: Optional[time] = self._coalesce(attrs, inst, "end_time", None)

        all_day_raw = self._coalesce(attrs, inst, "all_day", None)
        rec: str = self._coalesce(attrs, inst, "recurrence", Recurrence.ONE_TIME)

        # ВАЖНО: не используем "or 1", чтобы 0 не превратился в 1
        interval_val = self._coalesce(attrs, inst, "recurrence_interval", 1)
        try:
            interval = int(interval_val)
        except Exception:
            raise serializers.ValidationError({"recurrence_interval": _("Интервал должен быть числом.")})

        until: Optional[date] = self._coalesce(attrs, inst, "recurrence_until", None)
        rcount: Optional[int] = self._coalesce(attrs, inst, "recurrence_count", None)

        wmask: int = int(self._coalesce(attrs, inst, "weekdays_mask", 0))
        weekdays_input = attrs.get("weekdays", None)
        if weekdays_input is not None:
            try:
                wmask = self._weekdays_to_mask(weekdays_input)
            except Exception:
                raise serializers.ValidationError({"weekdays": _("Неверный формат дней недели (ожидаются числа 0..6).")})
            attrs["weekdays_mask"] = wmask
            attrs.pop("weekdays", None)

        color: Optional[str] = self._coalesce(attrs, inst, "color", None)

        # 1) База
        if interval < 1:
            raise serializers.ValidationError({"recurrence_interval": _("Интервал должен быть ≥ 1.")})
        if until is not None and until < s_date:
            raise serializers.ValidationError({"recurrence_until": _("Дата окончания повторения не может быть раньше даты начала.")})
        # Конфликтующие параметры
        if until is not None and rcount is not None:
            raise serializers.ValidationError({"recurrence_count": _("Нельзя одновременно задавать recurrence_until и recurrence_count.")})

        if color and not re.fullmatch(r"#([0-9A-Fa-f]{6})", color):
            raise serializers.ValidationError({"color": _("Цвет должен быть в формате #RRGGBB.")})

        # 2) Время / all_day
        has_any_time = (s_time is not None) or (e_time is not None)
        if has_any_time and (s_time is None or e_time is None):
            raise serializers.ValidationError(_("Если указываете время, заполните и начало, и окончание."))

        if all_day_raw is None:
            attrs["all_day"] = not has_any_time
        else:
            if all_day_raw and has_any_time:
                raise serializers.ValidationError(_("Нельзя указывать время для события на весь день."))
            if (all_day_raw is False) and not has_any_time:
                raise serializers.ValidationError(_("Для события с временем укажите start_time и end_time."))

        all_day: bool = attrs.get("all_day", inst.all_day if inst else (not has_any_time))

        # end_date по умолчанию = start_date
        if e_date is None:
            e_date = s_date
            attrs["end_date"] = e_date

        # 3) Хронология
        if all_day:
            if e_date < s_date:
                raise serializers.ValidationError({"end_date": _("Дата окончания не может быть раньше даты начала.")})
        else:
            start_dt = datetime.combine(s_date, s_time)
            end_dt = datetime.combine(e_date, e_time)
            if end_dt <= start_dt:
                raise serializers.ValidationError({"end_time": _("Окончание должно быть позже начала.")})

        # 4) Повторяемость
        if rec == Recurrence.HOURLY and all_day:
            raise serializers.ValidationError({"recurrence": _("Ежечасное повторение возможно только для событий с временем.")})

        if rec == Recurrence.WEEKLY:
            # create: требуем явные дни
            if is_create and wmask == 0:
                raise serializers.ValidationError({"weekdays_mask": _("Для еженедельного события укажите дни недели (weekdays или weekdays_mask).")})
            # update: если маска не пришла и осталась 0 — подставим день недели старта
            if (not is_create) and ("weekdays_mask" not in attrs) and (wmask == 0):
                wmask = 1 << s_date.weekday()
                attrs["weekdays_mask"] = wmask
            if wmask < 0 or wmask > 0b1111111:
                raise serializers.ValidationError({"weekdays_mask": _("Недопустимая маска дней недели.")})
        else:
            # для НЕ weekly игнорируем присланные weekdays/маску (если вдруг присланы пустыми)
            attrs.pop("weekdays", None)
            # маску не трогаем, если не прислана — оставляем как есть/0

        if rec not in Recurrence.values:
            raise serializers.ValidationError({"recurrence": _("Недопустимый тип повторения.")})

        if rcount is not None and rcount < 1:
            raise serializers.ValidationError({"recurrence_count": _("Количество повторов должно быть ≥ 1.")})

        return attrs

    def create(self, validated_data: Dict[str, Any]) -> CalendarEvent:
        validated_data.pop("weekdays", None)
        return CalendarEvent.objects.create(**validated_data)

    def update(self, instance: CalendarEvent, validated_data: Dict[str, Any]) -> CalendarEvent:
        validated_data.pop("weekdays", None)
        for f, v in validated_data.items():
            setattr(instance, f, v)
        instance.save()
        return instance


class CalendarEventSerializer(serializers.ModelSerializer):
    """Read-сериализатор (база модели, если нужен просмотр без развёртки)."""

    class Meta:
        model = CalendarEvent
        fields = "__all__"


class EventOccurrenceSerializer(serializers.Serializer):
    """Сериализатор одного материализованного вхождения для FullCalendar."""

    id = serializers.IntegerField()
    title = serializers.CharField()
    start = serializers.DateTimeField(required=False)
    end = serializers.DateTimeField(required=False)
    allDay = serializers.BooleanField()
    color = serializers.CharField(allow_null=True, required=False)
    recurrence = serializers.CharField()
    department_id = serializers.IntegerField(allow_null=True, required=False)
