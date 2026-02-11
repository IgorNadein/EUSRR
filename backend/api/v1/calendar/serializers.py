# backend/api/v1/calendar/serializers.py
from __future__ import annotations

import re
from datetime import date, datetime, time, timedelta
from typing import Any, Dict, List, Optional

from calendar_app.models import (
    Calendar,
    CalendarEvent,
    CalendarSubscription,
    Recurrence,
)
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
    calendar_id = serializers.IntegerField(required=False, allow_null=True)
    department_id = serializers.IntegerField(required=False, allow_null=True)
    employee_id = serializers.IntegerField(required=False, allow_null=True)

    class Meta:
        model = CalendarEvent
        fields = (
            "id",
            "calendar_id",
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
    def _coalesce(
        self,
        data: Dict[str, Any],
        instance: Optional[CalendarEvent],
        key: str,
        default=None,
    ):
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
            mask |= 1 << iv
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
            raise serializers.ValidationError(
                {"recurrence_interval": _("Интервал должен быть числом.")}
            )

        until: Optional[date] = self._coalesce(attrs, inst, "recurrence_until", None)
        rcount: Optional[int] = self._coalesce(attrs, inst, "recurrence_count", None)

        wmask: int = int(self._coalesce(attrs, inst, "weekdays_mask", 0))
        weekdays_input = attrs.get("weekdays", None)
        if weekdays_input is not None:
            try:
                wmask = self._weekdays_to_mask(weekdays_input)
            except Exception:
                raise serializers.ValidationError(
                    {
                        "weekdays": _(
                            "Неверный формат дней недели (ожидаются числа 0..6)."
                        )
                    }
                )
            attrs["weekdays_mask"] = wmask
            attrs.pop("weekdays", None)

        color: Optional[str] = self._coalesce(attrs, inst, "color", None)

        # 1) База
        if interval < 1:
            raise serializers.ValidationError(
                {"recurrence_interval": _("Интервал должен быть ≥ 1.")}
            )
        if until is not None and until < s_date:
            raise serializers.ValidationError(
                {
                    "recurrence_until": _(
                        "Дата окончания повторения не может быть раньше даты начала."
                    )
                }
            )
        # Конфликтующие параметры
        if until is not None and rcount is not None:
            raise serializers.ValidationError(
                {
                    "recurrence_count": _(
                        "Нельзя одновременно задавать recurrence_until и recurrence_count."
                    )
                }
            )

        if color and not re.fullmatch(r"#([0-9A-Fa-f]{6})", color):
            raise serializers.ValidationError(
                {"color": _("Цвет должен быть в формате #RRGGBB.")}
            )

        # 2) Время / all_day
        has_any_time = (s_time is not None) or (e_time is not None)
        if has_any_time and (s_time is None or e_time is None):
            raise serializers.ValidationError(
                _("Если указываете время, заполните и начало, и окончание.")
            )

        if all_day_raw is None:
            attrs["all_day"] = not has_any_time
        else:
            if all_day_raw and has_any_time:
                raise serializers.ValidationError(
                    _("Нельзя указывать время для события на весь день.")
                )
            if (all_day_raw is False) and not has_any_time:
                raise serializers.ValidationError(
                    _("Для события с временем укажите start_time и end_time.")
                )

        all_day: bool = attrs.get(
            "all_day", inst.all_day if inst else (not has_any_time)
        )

        # end_date по умолчанию = start_date
        if e_date is None:
            e_date = s_date
            attrs["end_date"] = e_date

        # 3) Хронология
        if all_day:
            if e_date < s_date:
                raise serializers.ValidationError(
                    {"end_date": _("Дата окончания не может быть раньше даты начала.")}
                )
        else:
            start_dt = datetime.combine(s_date, s_time)
            end_dt = datetime.combine(e_date, e_time)
            if end_dt <= start_dt:
                raise serializers.ValidationError(
                    {"end_time": _("Окончание должно быть позже начала.")}
                )

        # 4) Повторяемость
        if rec == Recurrence.HOURLY and all_day:
            raise serializers.ValidationError(
                {
                    "recurrence": _(
                        "Ежечасное повторение возможно только для событий с временем."
                    )
                }
            )

        if rec == Recurrence.WEEKLY:
            # create: требуем явные дни
            if is_create and wmask == 0:
                raise serializers.ValidationError(
                    {
                        "weekdays_mask": _(
                            "Для еженедельного события укажите дни недели (weekdays или weekdays_mask)."
                        )
                    }
                )
            # update: если маска не пришла и осталась 0 — подставим день недели старта
            if (not is_create) and ("weekdays_mask" not in attrs) and (wmask == 0):
                wmask = 1 << s_date.weekday()
                attrs["weekdays_mask"] = wmask
            if wmask < 0 or wmask > 0b1111111:
                raise serializers.ValidationError(
                    {"weekdays_mask": _("Недопустимая маска дней недели.")}
                )
        else:
            # для НЕ weekly игнорируем присланные weekdays/маску (если вдруг присланы пустыми)
            attrs.pop("weekdays", None)
            # маску не трогаем, если не прислана — оставляем как есть/0

        if rec not in Recurrence.values:
            raise serializers.ValidationError(
                {"recurrence": _("Недопустимый тип повторения.")}
            )

        if rcount is not None and rcount < 1:
            raise serializers.ValidationError(
                {"recurrence_count": _("Количество повторов должно быть ≥ 1.")}
            )

        return attrs

    def create(self, validated_data: Dict[str, Any]) -> CalendarEvent:
        validated_data.pop("weekdays", None)

        # Поддержка calendar_id (новая архитектура)
        calendar_id = validated_data.pop("calendar_id", None)
        if calendar_id is not None:
            from calendar_app.models import Calendar

            try:
                calendar = Calendar.objects.get(id=calendar_id)
                validated_data["calendar"] = calendar
            except Calendar.DoesNotExist:
                raise serializers.ValidationError(
                    {
                        "calendar_id": _("Календарь с ID {} не найден.").format(
                            calendar_id
                        )
                    }
                )

        # Legacy поддержка department_id и employee_id
        department_id = validated_data.pop("department_id", None)
        employee_id = validated_data.pop("employee_id", None)

        if department_id is not None:
            from employees.models import Department

            try:
                department = Department.objects.get(id=department_id)
                validated_data["department"] = department
            except Department.DoesNotExist:
                raise serializers.ValidationError(
                    {
                        "department_id": _("Отдел с ID {} не найден.").format(
                            department_id
                        )
                    }
                )

        if employee_id is not None:
            from django.contrib.auth import get_user_model

            User = get_user_model()
            try:
                employee = User.objects.get(id=employee_id)
                validated_data["employee"] = employee
            except User.DoesNotExist:
                raise serializers.ValidationError(
                    {
                        "employee_id": _("Сотрудник с ID {} не найден.").format(
                            employee_id
                        )
                    }
                )

        return CalendarEvent.objects.create(**validated_data)

    def update(
        self, instance: CalendarEvent, validated_data: Dict[str, Any]
    ) -> CalendarEvent:
        validated_data.pop("weekdays", None)

        # Поддержка calendar_id (новая архитектура)
        calendar_id = validated_data.pop("calendar_id", None)
        if calendar_id is not None:
            from calendar_app.models import Calendar

            try:
                calendar = Calendar.objects.get(id=calendar_id)
                validated_data["calendar"] = calendar
            except Calendar.DoesNotExist:
                raise serializers.ValidationError(
                    {
                        "calendar_id": _("Календарь с ID {} не найден.").format(
                            calendar_id
                        )
                    }
                )

        # Legacy поддержка department_id и employee_id
        department_id = validated_data.pop("department_id", None)
        employee_id = validated_data.pop("employee_id", None)

        if department_id is not None:
            from employees.models import Department

            try:
                department = Department.objects.get(id=department_id)
                validated_data["department"] = department
            except Department.DoesNotExist:
                raise serializers.ValidationError(
                    {
                        "department_id": _("Отдел с ID {} не найден.").format(
                            department_id
                        )
                    }
                )

        if employee_id is not None:
            from django.contrib.auth import get_user_model

            User = get_user_model()
            try:
                employee = User.objects.get(id=employee_id)
                validated_data["employee"] = employee
            except User.DoesNotExist:
                raise serializers.ValidationError(
                    {
                        "employee_id": _("Сотрудник с ID {} не найден.").format(
                            employee_id
                        )
                    }
                )

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


# ===== Сериализаторы для новых моделей Calendar и CalendarSubscription =====


class CalendarSerializer(serializers.ModelSerializer):
    """Сериализатор для календаря (чтение)."""

    owner_user_name = serializers.SerializerMethodField()
    owner_department_name = serializers.SerializerMethodField()
    event_count = serializers.IntegerField(read_only=True, required=False)
    subscriber_count = serializers.IntegerField(read_only=True, required=False)
    is_subscribed = serializers.SerializerMethodField()
    user_can_edit = serializers.SerializerMethodField()

    # Computed-поля для типа календаря
    is_personal = serializers.SerializerMethodField()
    is_department = serializers.SerializerMethodField()
    is_global = serializers.SerializerMethodField()

    class Meta:
        model = Calendar
        fields = (
            "id",
            "title",
            "description",
            "color",
            "icon",
            "visibility",
            "owner_user",
            "owner_user_name",
            "owner_department",
            "owner_department_name",
            "auto_subscribe_new_users",
            "auto_subscribe_department_members",
            "is_active",
            "created_at",
            "updated_at",
            "event_count",
            "subscriber_count",
            "is_subscribed",
            "user_can_edit",
            "is_personal",
            "is_department",
            "is_global",
        )
        read_only_fields = ("id", "created_at", "updated_at")

    def get_owner_user_name(self, obj):
        """Возвращает имя владельца-пользователя."""
        if obj.owner_user:
            return obj.owner_user.get_full_name() or obj.owner_user.username
        return None

    def get_owner_department_name(self, obj):
        """Возвращает название отдела-владельца."""
        return obj.owner_department.name if obj.owner_department else None

    def get_is_subscribed(self, obj):
        """Проверяет, подписан ли текущий пользователь."""
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            return obj.subscriptions.filter(user=request.user).exists()
        return False

    def get_is_personal(self, obj):
        """Проверяет, является ли календарь личным."""
        return obj.owner_user_id is not None and obj.owner_department_id is None

    def get_is_department(self, obj):
        """Проверяет, является ли календарь отдела."""
        return obj.owner_department_id is not None and obj.owner_user_id is None

    def get_is_global(self, obj):
        """Проверяет, является ли календарь глобальным."""
        return obj.owner_user_id is None and obj.owner_department_id is None

    def get_user_can_edit(self, obj):
        """Проверяет, может ли текущий пользователь редактировать календарь."""
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return False

        user = request.user

        # Админы могут всё
        if user.is_superuser or user.is_staff:
            return True

        # Владелец может редактировать
        if obj.owner_user_id == user.id:
            return True

        # Проверяем подписку с правом редактирования
        subscription = obj.subscriptions.filter(user=user).first()
        if subscription and (subscription.can_edit or subscription.can_manage):
            return True

        return False


class CalendarWriteSerializer(serializers.ModelSerializer):
    """Сериализатор для создания/обновления календаря."""

    class Meta:
        model = Calendar
        fields = (
            "id",
            "title",
            "description",
            "color",
            "icon",
            "visibility",
            "owner_user",
            "owner_department",
            "auto_subscribe_new_users",
            "auto_subscribe_department_members",
            "is_active",
        )
        read_only_fields = ("id",)

    def validate(self, attrs):
        """Валидация: нельзя одновременно указывать owner_user и owner_department."""
        owner_user = attrs.get("owner_user")
        owner_department = attrs.get("owner_department")

        # Для update нужно учитывать существующие значения
        if self.instance:
            owner_user = (
                owner_user if "owner_user" in attrs else self.instance.owner_user
            )
            owner_department = (
                owner_department
                if "owner_department" in attrs
                else self.instance.owner_department
            )

        if owner_user and owner_department:
            raise serializers.ValidationError(
                _("Календарь не может одновременно принадлежать пользователю и отделу.")
            )

        return attrs


class CalendarSubscriptionSerializer(serializers.ModelSerializer):
    """Сериализатор для подписки на календарь (чтение)."""

    calendar_title = serializers.CharField(source="calendar.title", read_only=True)
    calendar_color = serializers.CharField(source="calendar.color", read_only=True)
    user_name = serializers.SerializerMethodField()

    class Meta:
        model = CalendarSubscription
        fields = (
            "id",
            "calendar",
            "calendar_title",
            "calendar_color",
            "user",
            "user_name",
            "is_visible",
            "color_override",
            "can_edit",
            "can_manage",
            "notify_on_new_event",
            "notify_on_event_change",
            "subscribed_at",
        )
        read_only_fields = ("id", "subscribed_at")

    def get_user_name(self, obj):
        """Возвращает имя пользователя."""
        return obj.user.get_full_name() or obj.user.username


class CalendarSubscriptionWriteSerializer(serializers.ModelSerializer):
    """Сериализатор для создания/обновления подписки."""

    class Meta:
        model = CalendarSubscription
        fields = (
            "id",
            "calendar",
            "user",
            "is_visible",
            "color_override",
            "can_edit",
            "can_manage",
            "notify_on_new_event",
            "notify_on_event_change",
        )
        read_only_fields = ("id",)

    def validate(self, attrs):
        """Валидация подписки."""
        calendar = attrs.get("calendar") or (
            self.instance.calendar if self.instance else None
        )
        user = attrs.get("user") or (self.instance.user if self.instance else None)

        # Проверяем, что пользователь не подписывается на свой личный календарь дважды
        if calendar and user and calendar.owner_user_id == user.id:
            # Владелец может иметь подписку, но это optional
            pass

        return attrs
