# backend/api/v1/employees/views.py
from __future__ import annotations

from collections import defaultdict
from datetime import timedelta

import phonenumbers
from common.emails import send_templated_mail
from django.conf import settings
from django.contrib.auth.models import Group, Permission
from django.db import IntegrityError, transaction
from django.db.models import (Case, Count, Exists, F, IntegerField, OuterRef,
                              Prefetch, Q, Subquery, Value, When)
from django.utils import timezone
from django.utils.crypto import get_random_string
from employees.constants import ACTION_DISMISSED
from employees.models import (Department, DepartmentRole, Employee,
                              EmployeeAction, EmployeeDepartment, Position,
                              Skill)
from phonenumbers import PhoneNumberFormat
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import (AllowAny, DjangoModelPermissions,
                                        IsAdminUser, IsAuthenticated)
from rest_framework.response import Response
from rest_framework.views import APIView

from ..permissions import (ASSIGN_ROLE_PERM, MANAGE_PERM,
                           AdminOrActionOrModelPerms, IsDeptManagerForWrite,
                           IsSelfOrStaff)
from .serializers import (DepartmentRoleSerializer, DepartmentSerializer,
                          EmailSerializer, EmailVerifySerializer,
                          EmployeeActionSerializer, EmployeeListSerializer,
                          EmployeeSerializer, GroupSerializer,
                          PositionSerializer, RegisterSerializer,
                          SkillSerializer)


def _to_bool(val: str | None) -> bool | None:
    if val is None:
        return None
    s = str(val).strip().lower()
    if s in {"1", "true", "yes", "да"}:
        return True
    if s in {"0", "false", "no", "нет"}:
        return False
    return None


def _normalize_phone(raw: str | None) -> str | None:
    if not raw:
        return None
    if phonenumbers is None:
        return str(raw).strip()
    region = getattr(settings, "PHONE_DEFAULT_REGION", "RU")
    try:
        pn = phonenumbers.parse(str(raw), region)
        if not phonenumbers.is_valid_number(pn):
            return None
        return phonenumbers.format_number(pn, PhoneNumberFormat.E164)
    except Exception:
        return None


def _detect_phone_field() -> str | None:
    for n in ("phone", "phone_number", "mobile", "msisdn", "tel"):
        if any(f.name == n for f in Employee._meta.fields):
            return n
    return None


PHONE_FIELD = _detect_phone_field()


class HistoryActionMixin:
    """
    Добавляет GET /{basename}/{pk}/history/
    Параметры (необяз.): ?from=ISO ?to=ISO ?user=<id|email> ?type=+|~|-
    """

    history_diff_fields = None  # список полей для diff; если None — попытаемся угадать

    @action(detail=True, methods=["get"], permission_classes=[IsAuthenticated])
    def history(self, request, pk=None):
        obj = self.get_object()
        qs = obj.history.select_related("history_user").order_by(
            "-history_date", "-history_id"
        )

        q_from = request.query_params.get("from")
        q_to = request.query_params.get("to")
        q_user = request.query_params.get("user")
        q_type = request.query_params.get("type")

        if q_from:
            try:
                qs = qs.filter(history_date__gte=q_from)
            except:
                pass
        if q_to:
            try:
                qs = qs.filter(history_date__lte=q_to)
            except:
                pass
        if q_user:
            qs = qs.filter(
                Q(history_user__id__iexact=q_user)
                | Q(history_user__email__iexact=q_user)
            )
        if q_type in {"+", "~", "-"}:
            qs = qs.filter(history_type=q_type)

        items = list(qs)
        results = []
        for i, cur in enumerate(items):
            prev = items[i + 1] if i + 1 < len(items) else None
            changes = {}
            # какие поля сравнивать
            if self.history_diff_fields is not None:
                fields = self.history_diff_fields
            else:
                # берём только реальные field.name модели (без M2M)
                fields = [f.name for f in obj._meta.fields]

            for name in fields:
                new = getattr(cur, name, None)
                old = getattr(prev, name, None) if prev else None
                if old != new:
                    changes[name] = {"old": old, "new": new}

            results.append(
                {
                    "history_id": cur.history_id,
                    "history_date": cur.history_date,
                    "history_type": cur.history_type,  # "+", "~", "-"
                    "history_user": getattr(cur.history_user, "email", None),
                    "changes": changes,
                }
            )
        return Response({"count": len(results), "results": results})


class ResendEmailAPIView(APIView):
    """POST /api/v1/auth/resend-email/  body: {"email": "..."}"""

    throttle_scope = "anon"
    permission_classes = [AllowAny]

    def post(self, request):
        ser = EmailSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        email = ser.validated_data["email"]

        user = Employee.objects.filter(email__iexact=email).first()
        if not user:
            return Response({"ok": False, "error": "user_not_found"}, status=404)
        if user.email_verified:
            return Response({"ok": False, "error": "already_verified"}, status=400)

        user.email_activation_code = get_random_string(6, "0123456789")
        user.save(update_fields=["email_activation_code"])

        send_templated_mail(
            subject="Подтверждение регистрации",
            to=[user.email],
            template_base="emails/registration_verify_code",
            context={"code": user.email_activation_code, "user": user},
        )
        return Response({"ok": True}, status=200)


class VerifyEmailAPIView(APIView):
    throttle_scope = "anon"
    permission_classes = [AllowAny]

    def post(self, request):
        ser = EmailVerifySerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        email = ser.validated_data["email"]
        code = ser.validated_data["code"].strip()

        user = Employee.objects.filter(email__iexact=email).first()
        if not user:
            return Response({"ok": False, "error": "user_not_found"}, status=404)
        if not code:
            return Response({"ok": False, "error": "empty_code"}, status=400)

        created = getattr(user, "created_at", None) or getattr(
            user, "date_joined", None
        )
        if created and not user.email_verified:
            if timezone.now() - created > timedelta(minutes=5):
                user.delete()
                return Response({"ok": False, "error": "expired"}, status=400)

        if user.verify_email(code):
            return Response({"ok": True, "user_id": user.id}, status=200)
        return Response({"ok": False, "error": "invalid_code"}, status=400)


class RegisterAPIView(APIView):
    """
    POST /api/v1/auth/register/
    Требует: first_name, last_name, phone_number, email, birth_date, password,
             и хотя бы один из: telegram / whatsapp / wechat
    """

    throttle_scope = "anon"
    permission_classes = [AllowAny]

    @transaction.atomic
    def post(self, request):
        if not (
            request.data.get("telegram")
            or request.data.get("whatsapp")
            or request.data.get("wechat")
        ):
            return Response(
                {
                    "detail": "Заполните хотя бы одно из полей: WhatsApp, WeChat или Telegram"
                },
                status=400,
            )

        ser = RegisterSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        v = ser.validated_data

        email = v["email"].strip().lower()
        password = v["password"]
        phone_raw = v.get("phone_number") or request.data.get("phone")
        phone_norm = _normalize_phone(phone_raw)

        # Телефон обязателен и должен быть валиден (E.164)
        if not phone_norm:
            return Response({"ok": False, "error": "invalid_phone"}, status=400)

        # 1) Дубликат телефона — жёстко 400
        if Employee.objects.filter(phone_number=phone_norm).exists():
            return Response({"ok": False, "error": "phone_taken"}, status=400)

        # 2) Логика по email
        user = Employee.objects.filter(email__iexact=email).first()
        if user and user.email_verified:
            return Response({"ok": False, "error": "email_taken"}, status=400)
        if user and not user.email_verified:
            # без регенерации кода/письма — просто мягкий ответ
            return Response(
                {"ok": True, "pending_verification": True, "user_id": user.id},
                status=200,
            )

        # 3) Создание нового
        extra = {
            "first_name": v["first_name"],
            "last_name": v["last_name"],
            "birth_date": v["birth_date"],
            "telegram": v.get("telegram", ""),
            "whatsapp": v.get("whatsapp", ""),
            "wechat": v.get("wechat", ""),
        }
        phone_for_create = phone_norm

        try:
            user = Employee.objects.create_user(
                email=email,
                password=password,
                phone_number=phone_for_create,
                **extra,
            )

        except IntegrityError as e:
            msg = str(e).lower()
            if "phone" in msg or "phone_number" in msg:
                return Response({"ok": False, "error": "phone_taken"}, status=400)
            if "email" in msg:
                return Response({"ok": False, "error": "email_taken"}, status=400)
            raise

        # доп. поля
        pos_id = v.get("position")
        if pos_id:
            Position.objects.filter(pk=pos_id).first() and setattr(
                user, "position_id", pos_id
            )
        skills_ids = v.get("skills") or []
        if skills_ids:
            user.skills.set(Skill.objects.filter(pk__in=skills_ids))
        user.save()

        return Response(
            {
                "id": user.id,
                "email": user.email,
                "email_verified": user.email_verified,
                "is_active": user.is_active,
            },
            status=status.HTTP_201_CREATED,
        )


class DepartmentViewSet(HistoryActionMixin, viewsets.ModelViewSet):
    """
    /api/departments/
      - GET (list/detail)     — только аутентифицированные пользователи
      - POST/DELETE           — только staff/superuser или пользователи с правами
      - PATCH/PUT             — руководитель отдела ИЛИ роль с perm "manage_department"
      - Смена head            — руководитель отдела ИЛИ роль с perm "change_department_head"
      - Управление ролями     — руководитель отдела ИЛИ роль с perm "assign_department_role"
    """

    serializer_class = DepartmentSerializer
    permission_classes = [IsAuthenticated]
    search_fields = ["name", "description"]
    ordering = ["name"]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    history_diff_fields = ["name", "description", "head_id", "head_appointed_at"]

    def get_queryset(self):
        # подзапрос: есть ли head среди связей отдела
        head_in_links_qs = EmployeeDepartment.objects.filter(
            department=OuterRef("pk"),
            employee_id=OuterRef("head_id"),
            is_active=True,
        )

        return (
            Department.objects.select_related("head")
            .annotate(
                active_links_count=Count(
                    "employeedepartment",
                    filter=Q(employeedepartment__is_active=True),
                    distinct=True,
                ),
                # +1, если head задан и не присутствует среди активных связей
                head_extra=Case(
                    When(
                        Q(head__isnull=False) & ~Exists(head_in_links_qs),
                        then=Value(1),
                    ),
                    default=Value(0),
                    output_field=IntegerField(),
                ),
            )
            .annotate(employees_count=F("active_links_count") + F("head_extra"))
        )

    def get_permissions(self):
        # Создание/удаление — только админы
        if self.action in ["create", "destroy"]:
            return [AdminOrActionOrModelPerms()]
        # Общие правки отдела — право manage_department на объекте
        if self.action in ["update", "partial_update"]:
            self.required_perm_code = "manage_department"
            return [IsAuthenticated(), IsDeptManagerForWrite()]
        return super().get_permissions()

    def perform_create(self, serializer):
        # head_appointed_at у тебя auto_now — обновится сам
        serializer.save()

    def _check_head_change_perm(self, request, dept: Department) -> Response | None:
        if "head_id" not in request.data:
            return None
        raw = request.data.get("head_id", None)
        if raw is None:
            new_head_id = None
        else:
            try:
                new_head_id = int(raw)
            except (TypeError, ValueError):
                new_head_id = None
        if new_head_id != dept.head_id:
            self.required_perm_code = "change_department_head"
            perm = IsDeptManagerForWrite()
            if not perm.has_object_permission(request, self, dept):
                return Response(
                    {"detail": "Недостаточно прав для смены руководителя отдела"},
                    status=status.HTTP_403_FORBIDDEN,
                )
        return None

    def partial_update(self, request, *args, **kwargs):
        dept = self.get_object()
        resp = self._check_head_change_perm(request, dept)
        if resp is not None:
            return resp
        return super().partial_update(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        dept = self.get_object()
        resp = self._check_head_change_perm(request, dept)
        if resp is not None:
            return resp
        return super().update(request, *args, **kwargs)

    @action(detail=True, methods=["post"])
    def set_head(self, request, pk=None):
        dept: Department = self.get_object()
        self.required_perm_code = "change_department_head"
        perm = IsDeptManagerForWrite()
        if not perm.has_object_permission(request, self, dept):
            return Response(
                {"detail": "Недостаточно прав для смены руководителя отдела"},
                status=status.HTTP_403_FORBIDDEN,
            )

        if "head_id" not in request.data:
            return Response(
                {
                    "detail": "Параметр 'head_id' обязателен (null — чтобы снять руководителя)."
                },
                status=400,
            )

        head_id = request.data.get("head_id", None)

        # снять руководителя (явно передан null)
        if head_id is None:
            if dept.head_id is not None:
                dept.head = None
                dept.save(update_fields=["head"])  # auto_now обновит head_appointed_at
            return Response(status=status.HTTP_204_NO_CONTENT)

        try:
            emp = Employee.objects.get(pk=head_id)
        except Employee.DoesNotExist:
            return Response({"detail": "Сотрудник не найден"}, status=404)

        if not emp.is_actually_active:
            return Response({"detail": "Сотрудник неактивен"}, status=400)

        if dept.head_id != emp.id:
            dept.head = emp
            dept.save(update_fields=["head"])
        return Response({"head_id": dept.head_id}, status=200)

    @action(detail=True, methods=["post"])
    def set_member_role(self, request, pk=None):
        """
        Body:
          {
            "employee_id": 123,
            "role_id": 7 | null,   # null = снять роль (оставив сотрудника в отделе)
            "is_active": true|false (необязательно)
          }
        """
        dept: Department = self.get_object()

        self.required_perm_code = "assign_department_role"
        perm = IsDeptManagerForWrite()
        if not perm.has_object_permission(request, self, dept):
            return Response(
                {"detail": "Недостаточно прав для управления ролями отдела"},
                status=status.HTTP_403_FORBIDDEN,
            )

        employee_id = request.data.get("employee_id")
        role_id = request.data.get("role_id", None)
        is_active = request.data.get("is_active", None)

        if not employee_id:
            return Response({"detail": "employee_id обязателен"}, status=400)

        try:
            emp = Employee.objects.get(pk=employee_id)
        except Employee.DoesNotExist:
            return Response({"detail": "Сотрудник не найден"}, status=404)

        role = None
        if role_id is not None:
            try:
                role = DepartmentRole.objects.get(pk=role_id)
            except DepartmentRole.DoesNotExist:
                return Response({"detail": "Роль не найдена"}, status=404)
            if role.department_id != dept.id:
                return Response(
                    {"detail": "Роль принадлежит другому отделу"}, status=400
                )

        with transaction.atomic():
            link, _ = EmployeeDepartment.objects.select_for_update().get_or_create(
                employee=emp, department=dept, defaults={"is_active": True}
            )
            link.role = role
            if is_active is not None:
                link.is_active = bool(is_active)
            link.full_clean()
            link.save()

        return Response(
            {
                "employee_id": emp.id,
                "role_id": role.id if role else None,
                "is_active": link.is_active,
            },
            status=200,
        )


class EmployeeViewSet(viewsets.ModelViewSet):
    """
    /api/v1/employees/

    Доступ:
      - GET list/retrieve          — только аутентифицированные пользователи.
      - POST (create)              — только staff/superuser (в методе create есть явная проверка).
      - PATCH/PUT/DELETE {id}      — staff/superuser ИЛИ пользователи с модельными правами
                                     на Employee (через AdminOrActionOrModelPerms).
      - GET/PATCH /employees/me/   — только аутентифицированные; PATCH правит профиль текущего пользователя.
      - POST {id}/add_skill|remove_skill — требуется спец-пермишен
                                     "employees.manage_employee_skills" ИЛИ staff/superuser
                                     (через AdminOrActionOrModelPerms).

    Поиск: last_name, first_name, patronymic, email, phone_number

    Фильтры:
      ?department=<id>            — участники отдела + head
      ?position=<id>              — по должности
      ?skill=<id>&skill=<id>      — любые из навыков (OR)
      ?email_verified=true|false
      ?active=true|false
      ?actually_active=true|false — реально активные: email_verified=True и не DISMISSED
                                    (или нет действий, но is_active=True)

    Сортировка:
      ?ordering=last_name|first_name|created_at|id  (+ '-' для DESC)

    Примечания:
      - В detail/retrieve и в me мы добавляем в контекст сериализатора флаги
        include_actions и include_action_history — в ответе придут кадровые
        события сотрудника и их история.
      - Создание /employees/ доступно ТОЛЬКО staff/superuser, даже если у пользователя
        есть модельный пермишен add_employee (это отмечено явно в create()).
    """

    serializer_class = EmployeeSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["last_name", "first_name", "patronymic", "email", "phone_number"]
    ordering_fields = ["last_name", "first_name", "created_at", "id"]
    ordering = ["last_name", "first_name"]
    required_perms_by_action = {
        "add_skill": "employees.manage_employee_skills",
        "remove_skill": "employees.manage_employee_skills",
    }

    def get_permissions(self):
        # create: только staff/superuser (перепроверяете и в методе create)
        if self.action == "create":
            return [IsAuthenticated(), AdminOrActionOrModelPerms()]

        # update/partial_update/destroy: владелец ИЛИ админ/модельные пермишены
        if self.action in {
            "update",
            "partial_update",
            "destroy",
            "add_skill",
            "remove_skill",
        }:
            return [IsAuthenticated(), (IsSelfOrStaff | AdminOrActionOrModelPerms)()]

        # list / retrieve / me -> только аутентификация
        return [IsAuthenticated()]

    def get_queryset(self):
        last_action_code_sq = Subquery(
            EmployeeAction.objects.filter(employee_id=OuterRef("pk"))
            .order_by("-date")
            .values("action")[:1]
        )
        dep_links_prefetch = Prefetch(
            "departments_links",
            queryset=EmployeeDepartment.objects.filter(is_active=True).select_related(
                "department", "role"
            ),
            to_attr="dept_links",
        )

        prefetches = [
            "skills",
            dep_links_prefetch,
            Prefetch("actions", queryset=EmployeeAction.objects.order_by("-date")),
        ]

        qs = (
            Employee.objects.select_related("position")
            .prefetch_related(*prefetches)
            .annotate(last_action_code=last_action_code_sq)
            .order_by(*self.ordering)
        )

        qp = self.request.query_params

        # по отделу: связи + руководитель
        dep = qp.get("department")
        if dep:
            try:
                dep_id = int(dep)
            except (TypeError, ValueError):
                dep_id = None
            if dep_id:
                member_ids = EmployeeDepartment.objects.filter(
                    department_id=dep_id
                ).values("employee_id")
                head_ids = Department.objects.filter(id=dep_id).values("head_id")
                qs = qs.filter(Q(id__in=member_ids) | Q(id__in=head_ids))

        # по должности
        position = qp.get("position")
        if position:
            qs = qs.filter(position_id=position)

        # по навыкам (any-of)
        skill_ids = qp.getlist("skill")
        if skill_ids:
            qs = qs.filter(skills__in=skill_ids).distinct()

        # статусы
        email_verified = _to_bool(qp.get("email_verified"))
        if email_verified is not None:
            qs = qs.filter(email_verified=email_verified)

        active = _to_bool(qp.get("active"))
        if active is not None:
            qs = qs.filter(is_active=active)

        # реально активен
        actually = _to_bool(qp.get("actually_active"))
        if actually is True:
            qs = qs.filter(
                Q(email_verified=True)
                & (
                    Q(last_action_code__isnull=True, is_active=True)
                    | ~Q(last_action_code=ACTION_DISMISSED)
                )
            )
        elif actually is False:
            qs = qs.exclude(
                Q(email_verified=True)
                & (
                    Q(last_action_code__isnull=True, is_active=True)
                    | ~Q(last_action_code=ACTION_DISMISSED)
                )
            )

        return qs

    def get_serializer_class(self):
        # для списка отдаём облегчённый, но с нужными полями
        if self.action == "list":
            return EmployeeListSerializer
        return EmployeeSerializer

    def create(self, request, *args, **kwargs):
        if not (request.user.is_staff or request.user.is_superuser):
            return Response(
                {"detail": "Only staff can create users."},
                status=status.HTTP_403_FORBIDDEN,
            )

        ser = self.get_serializer(data=request.data)
        ser.is_valid(raise_exception=True)
        vd = dict(ser.validated_data)

        # Бизнес-валидация контактов
        if not (vd.get("whatsapp") or vd.get("telegram") or vd.get("wechat")):
            return Response(
                {
                    "detail": "Заполните хотя бы одно из полей: WhatsApp, WeChat или Telegram"
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # пароль
        password = request.data.get("password")
        if not password:
            import secrets

            password = secrets.token_urlsafe(12)

        # вынести из vd, чтобы не передать дважды
        email = vd.pop("email", None)
        phone_number = vd.pop("phone_number", None)
        if not email or not phone_number:
            return Response(
                {"detail": "email и phone_number обязательны для создания."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        skills = vd.pop("skills_ids", [])

        # теперь в vd нет email/phone_number — дублирования не будет
        user = Employee.objects.create_user(
            email=email,
            password=password,
            phone_number=phone_number,
            **vd,  # avatar / names / position и т.п.
        )
        if skills:
            user.skills.set(skills)

        out = self.get_serializer(user)
        headers = self.get_success_headers(out.data)
        return Response(out.data, status=status.HTTP_201_CREATED, headers=headers)

    @action(detail=False, methods=["get", "patch"])
    def me(self, request):
        """
        GET   /api/v1/employees/me/      — ваш профиль (ТОТ ЖЕ формат, что retrieve)
        PATCH /api/v1/employees/me/      — частичное обновление своего профиля
        """
        instance: Employee = request.user  # type: ignore

        if request.method == "GET":
            instance = (
                Employee.objects.select_related("position")
                .prefetch_related(
                    "skills",
                    Prefetch(
                        "departments_links",
                        queryset=EmployeeDepartment.objects.filter(
                            is_active=True
                        ).select_related("department", "role"),
                        to_attr="dept_links",
                    ),
                    Prefetch(
                        "actions", queryset=EmployeeAction.objects.order_by("-date")
                    ),
                )
                .get(pk=request.user.pk)
            )
            ctx = self.get_serializer_context()
            ctx["include_actions"] = True
            ctx["include_action_history"] = True
            data = self.get_serializer(instance, context=ctx).data
            return Response(data, status=status.HTTP_200_OK)
        ser = self.get_serializer(instance, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)

        vd = ser.validated_data
        if all(k not in vd for k in ("whatsapp", "telegram", "wechat")):
            new_whatsapp = vd.get("whatsapp", instance.whatsapp)
            new_telegram = vd.get("telegram", instance.telegram)
            new_wechat = vd.get("wechat", instance.wechat)
            if not (new_whatsapp or new_telegram or new_wechat):
                return Response(
                    {
                        "detail": "Должен быть указан хотя бы один канал связи (WhatsApp/Telegram/WeChat)."
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

        ser.save()
        return Response(ser.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"])
    def add_skill(self, request, pk=None):
        """
        body: { "skill_id": 3 } ИЛИ { "skill_name": "Python" }
        """
        emp = self.get_object()
        sid = request.data.get("skill_id")
        sname = (request.data.get("skill_name") or "").strip()

        sk = None
        if sid:
            sk = Skill.objects.filter(pk=sid).first()
        if not sk and sname:
            sk = Skill.objects.filter(
                name__iexact=sname
            ).first() or Skill.objects.create(name=sname)
        if not sk:
            return Response({"detail": "Навык не найден/не указан"}, status=400)

        emp.skills.add(sk)
        return Response(
            {"ok": True, "skill": {"id": sk.id, "name": sk.name}}, status=200
        )

    @action(detail=True, methods=["post"])
    def remove_skill(self, request, pk=None):
        """
        body: { "skill_id": 3 } ИЛИ { "skill_name": "Python" }
        """
        emp = self.get_object()
        sid = request.data.get("skill_id")
        sname = (request.data.get("skill_name") or "").strip()

        sk = None
        if sid:
            sk = Skill.objects.filter(pk=sid).first()
        if not sk and sname:
            sk = Skill.objects.filter(name__iexact=sname).first()
        if not sk:
            return Response({"detail": "Навык не найден"}, status=404)

        emp.skills.remove(sk)
        return Response(
            {"ok": True, "removed": {"id": sk.id, "name": sk.name}}, status=200
        )

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        if getattr(self, "action", None) in {"retrieve", "me"}:
            ctx["include_actions"] = True
            ctx["include_action_history"] = True
        return ctx


class PositionViewSet(HistoryActionMixin, viewsets.ModelViewSet):
    """
    /api/v1/positions/
      GET list/retrieve   — аутентифицированные
      POST/PUT/PATCH/DEL  — staff/superuser ИЛИ пользователь с model perms
      Экшены:
        POST /{id}/set-groups
        POST /{id}/add-groups
        POST /{id}/remove-groups
        GET  /{id}/permissions
    """

    queryset = Position.objects.all().prefetch_related("groups")
    serializer_class = PositionSerializer
    pagination_class = None
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["name", "description"]
    ordering_fields = ["name", "id"]
    ordering = ["name"]
    history_diff_fields = ["name", "description"]
    permission_classes = [IsAuthenticated, AdminOrActionOrModelPerms]
    required_perms_by_action = {
        "set_groups": "employees.assign_position_groups",
        "add_groups": "employees.assign_position_groups",
        "remove_groups": "employees.assign_position_groups",
    }

    def _validate_groups_payload(self, request):
        ids = request.data.get("groups")
        if not isinstance(ids, list):
            return None, Response(
                {"detail": "Поле 'groups' должно быть списком id"}, status=400
            )
        qs = Group.objects.filter(id__in=ids)
        if qs.count() != len(set(ids)):
            return None, Response({"detail": "Некоторые группы не найдены"}, status=400)
        return qs, None

    @action(detail=True, methods=["post"])
    def set_groups(self, request, pk=None):
        pos = self.get_object()
        qs, err = self._validate_groups_payload(request)
        if err:
            return err
        pos.groups.set(qs)
        return Response(
            {"ok": True, "group_ids": list(pos.groups.values_list("id", flat=True))},
            status=200,
        )

    @action(detail=True, methods=["post"])
    def add_groups(self, request, pk=None):
        pos = self.get_object()
        qs, err = self._validate_groups_payload(request)
        if err:
            return err
        pos.groups.add(*qs)
        return Response(
            {"ok": True, "group_ids": list(pos.groups.values_list("id", flat=True))},
            status=200,
        )

    @action(detail=True, methods=["post"])
    def remove_groups(self, request, pk=None):
        pos = self.get_object()
        qs, err = self._validate_groups_payload(request)
        if err:
            return err
        pos.groups.remove(*qs)
        return Response(
            {"ok": True, "group_ids": list(pos.groups.values_list("id", flat=True))},
            status=200,
        )

    @action(detail=True, methods=["get"])
    def permissions(self, request, pk=None):
        pos = self.get_object()
        perms = (
            Permission.objects.filter(group__positions=pos)
            .select_related("content_type")
            .distinct()
        )
        data = [
            {
                "id": p.id,
                "codename": f"{p.content_type.app_label}.{p.codename}",
                "name": p.name,
                "app": p.content_type.app_label,
                "model": p.content_type.model,
            }
            for p in perms
        ]
        return Response({"count": len(data), "results": data}, status=200)


class DepartmentRoleViewSet(viewsets.ModelViewSet):
    """
    /api/v1/positions/
    GET list/retrieve                 — IsAuthenticated
    POST/PUT/PATCH/DELETE            — Admin OR Django model perms (add/change/delete_position)
    POST /{id}/set-groups            — Admin OR employees.assign_position_groups
    POST /{id}/add-groups            — Admin OR employees.assign_position_groups
    POST /{id}/remove-groups         — Admin OR employees.assign_position_groups
    GET  /{id}/permissions           — IsAuthenticated
    """

    serializer_class = DepartmentRoleSerializer
    permission_classes = [IsAuthenticated, IsDeptManagerForWrite]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["name"]
    ordering_fields = ["name", "id"]
    ordering = ["name"]
    pagination_class = None

    def get_queryset(self):
        qs = DepartmentRole.objects.select_related("department").prefetch_related(
            "permissions__content_type"
        )
        dep = self.request.query_params.get("department")
        if dep:
            try:
                dep_id = int(dep)
            except (TypeError, ValueError):
                # нечисловой параметр -> пустой список без ошибки
                return DepartmentRole.objects.none()
            qs = qs.filter(department_id=dep_id)
        return qs

    # --- аккуратно задаём требуемые права под экшены ---
    def get_permissions(self):
        # по умолчанию чтение — только аутентификация
        if self.action in ("create", "update", "partial_update", "destroy"):
            self.required_perm_code = MANAGE_PERM
        elif self.action in ("set_perms", "add_perms", "remove_perms"):
            self.required_perm_code = ASSIGN_ROLE_PERM
        else:
            self.required_perm_code = None
        return super().get_permissions()

    # create — объект ещё не существует, делаем явную проверку на отдел
    def perform_create(self, serializer):
        dept: Department = serializer.validated_data["department"]
        checker = IsDeptManagerForWrite()
        if not checker.has_object_permission(self.request, self, dept):
            from rest_framework.exceptions import PermissionDenied

            raise PermissionDenied(
                "Недостаточно прав для управления ролями этого отдела"
            )
        serializer.save()

    # update/destroy — has_object_permission отработает, т.к. мы добавили IsDeptManagerForWrite
    # и он умеет извлекать department из объекта роли (см. патч выше)

    # ---- экшены управления правами роли ----
    def _validate_perm_ids(self, request):
        ids = request.data.get("permission_ids")
        if not isinstance(ids, list):
            return None, Response(
                {"detail": "Поле 'permission_ids' должно быть списком id"}, status=400
            )
        perms = Permission.objects.filter(id__in=ids).select_related("content_type")
        if perms.count() != len(set(ids)):
            return None, Response(
                {"detail": "Некоторые permissions не найдены"}, status=400
            )
        return perms, None

    @action(detail=True, methods=["get"])
    def perms(self, request, pk=None):
        role: DepartmentRole = self.get_object()
        data = [
            {
                "id": p.id,
                "codename": f"{p.content_type.app_label}.{p.codename}",
                "name": p.name,
            }
            for p in role.permissions.select_related("content_type").all()
        ]
        return Response({"count": len(data), "results": data})

    @action(detail=True, methods=["post"])
    def set_perms(self, request, pk=None):
        role: DepartmentRole = self.get_object()
        # required_perm_code уже выставлен -> IsDeptManagerForWrite проверит доступ по role.department
        perms, err = self._validate_perm_ids(request)
        if err:
            return err
        role.permissions.set(perms)
        return Response(
            {
                "ok": True,
                "permission_ids": list(role.permissions.values_list("id", flat=True)),
            }
        )

    @action(detail=True, methods=["post"])
    def add_perms(self, request, pk=None):
        role: DepartmentRole = self.get_object()
        perms, err = self._validate_perm_ids(request)
        if err:
            return err
        role.permissions.add(*perms)
        return Response(
            {
                "ok": True,
                "permission_ids": list(role.permissions.values_list("id", flat=True)),
            }
        )

    @action(detail=True, methods=["post"])
    def remove_perms(self, request, pk=None):
        role: DepartmentRole = self.get_object()
        perms, err = self._validate_perm_ids(request)
        if err:
            return err
        role.permissions.remove(*perms)
        return Response(
            {
                "ok": True,
                "permission_ids": list(role.permissions.values_list("id", flat=True)),
            }
        )


class SkillViewSet(viewsets.ModelViewSet):
    """
    /api/v1/skills/
      - GET list/retrieve      — IsAuthenticated
      - POST (create)          — IsAuthenticated (любой авторизованный может создавать новые навыки)
      - PATCH/PUT              — staff/superuser ИЛИ perm employees.change_skill
      - DELETE                 — staff/superuser ИЛИ perm employees.delete_skill
    Экшены:
      - POST /skills/bulk_create   — как create (любой авторизованный)
      - POST /skills/merge         — объединить source->target (perm employees.change_skill)
        body: {
          "source_id": 1,
          "target_id": 2,
          "reassign": true,         # переназначить сотрудникам source -> target (по умолч. true)
          "delete_source": true     # удалить исходный навык после переназначения (по умолч. true)
        }
    """

    queryset = Skill.objects.all().order_by("name")
    serializer_class = SkillSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["name"]
    ordering_fields = ["name", "id"]
    ordering = ["name"]
    pagination_class = None
    required_perms_by_action = {
        "merge": "employees.change_skill",
    }

    def get_permissions(self):
        if self.action in ("create", "bulk_create"):
            return [IsAuthenticated()]
        return [IsAuthenticated(), AdminOrActionOrModelPerms()]

    @action(detail=False, methods=["post"])
    def bulk_create(self, request):
        names = request.data.get("names")
        if not isinstance(names, list) or not names:
            return Response(
                {"detail": "Поле 'names' должно быть непустым списком строк"},
                status=400,
            )

        # нормализация: trim + отбраковка пустых, дедуп (case-insensitive)
        cleaned = []
        seen = set()
        for n in names:
            if not isinstance(n, str):
                continue
            s = n.strip()
            if not s:
                continue
            key = s.lower()
            if key in seen:
                continue
            seen.add(key)
            cleaned.append(s)

        # отфильтруем уже существующие (по точному совпадению имени)
        existing = set(
            Skill.objects.filter(name__in=cleaned).values_list("name", flat=True)
        )
        to_create = [Skill(name=n) for n in cleaned if n not in existing]
        Skill.objects.bulk_create(to_create, ignore_conflicts=True)

        created = Skill.objects.filter(
            name__in=[n for n in cleaned if n not in existing]
        ).order_by("name")
        return Response(
            {
                "created_count": created.count(),
                "created": SkillSerializer(created, many=True).data,
            },
            status=201,
        )

    @action(detail=False, methods=["post"])
    @transaction.atomic
    def merge(self, request):
        """
        Заменяет навык source на target, опционально переносит всех сотрудников и удаляет source.
        Требуется право employees.change_skill.
        """
        sid = request.data.get("source_id")
        tid = request.data.get("target_id")
        reassign = bool(request.data.get("reassign", True))
        delete_source = bool(request.data.get("delete_source", True))

        if not sid or not tid:
            return Response({"detail": "source_id и target_id обязательны"}, status=400)
        try:
            sid = int(sid)
            tid = int(tid)
        except (TypeError, ValueError):
            return Response(
                {"detail": "source_id и target_id должны быть числами"}, status=400
            )
        if sid == tid:
            return Response(
                {"detail": "source_id и target_id не должны совпадать"}, status=400
            )

        try:
            source = Skill.objects.get(pk=sid)
            target = Skill.objects.get(pk=tid)
        except Skill.DoesNotExist:
            return Response({"detail": "Skill не найден"}, status=404)

        moved_count = 0
        if reassign:
            # переназначить всем сотрудникам: source -> target
            qs = Employee.objects.filter(skills=source).only("id").distinct()
            for emp in qs:
                emp.skills.add(target)
                emp.skills.remove(source)
                moved_count += 1

        # удалить исходный навык при необходимости
        if delete_source:
            source.delete()

        return Response(
            {
                "ok": True,
                "source_id": sid,
                "target_id": tid,
                "reassigned_employees": moved_count,
                "source_deleted": bool(delete_source),
            },
            status=200,
        )


class EmployeeActionViewSet(HistoryActionMixin, viewsets.ModelViewSet):
    """
    /api/v1/employee-actions/
      - GET list/retrieve  — IsAuthenticated
      - POST create        — staff/superuser ИЛИ perm employees.add_employeeaction
      - PATCH/PUT update   — staff/superuser ИЛИ perm employees.change_employeeaction
      - DELETE destroy     — staff/superuser ИЛИ perm employees.delete_employeeaction

    Фильтры:
      ?employee=<id>   — по сотруднику
      ?date_from=ISO   — >=
      ?date_to=ISO     — <=
    """

    serializer_class = EmployeeActionSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ["date", "id"]
    ordering = ["-date"]
    pagination_class = None
    history_diff_fields = ["action", "date", "comment", "extra", "employee_id"]

    def get_queryset(self):
        qs = EmployeeAction.objects.select_related("employee").order_by(*self.ordering)
        qp = self.request.query_params
        emp = qp.get("employee")
        if emp:
            try:
                emp_id = int(emp)
                qs = qs.filter(employee_id=emp_id)
            except (TypeError, ValueError):
                return EmployeeAction.objects.none()
        df = qp.get("date_from")
        dt = qp.get("date_to")
        if df:
            try:
                qs = qs.filter(date__gte=df)
            except Exception:
                pass
        if dt:
            try:
                qs = qs.filter(date__lte=dt)
            except Exception:
                pass
        return qs

    # --- права на запись через модельные пермишены ---
    def get_permissions(self):
        if self.action == "create":
            self.required_perm_code = "employees.add_employeeaction"
            return [IsAuthenticated(), AdminOrActionOrModelPerms()]
        if self.action in ("update", "partial_update"):
            self.required_perm_code = "employees.change_employeeaction"
            return [IsAuthenticated(), AdminOrActionOrModelPerms()]
        if self.action == "destroy":
            self.required_perm_code = "employees.delete_employeeaction"
            return [IsAuthenticated(), AdminOrActionOrModelPerms()]
        self.required_perm_code = None
        return super().get_permissions()

    # --- бизнес-эффекты после записи события ---
    def _apply_effects(self, action_obj: EmployeeAction):
        emp = action_obj.employee
        if action_obj.action == ACTION_DISMISSED:
            # деактивируем сотрудника и связи
            EmployeeDepartment.objects.filter(employee=emp, is_active=True).update(
                is_active=False, date_to=timezone.now().date()
            )
            if emp.is_active:
                emp.is_active = False
                emp.save(update_fields=["is_active"])
        else:
            # любое иное событие делает сотрудника активным
            if not emp.is_active:
                emp.is_active = True
                emp.save(update_fields=["is_active"])

    @transaction.atomic
    def perform_create(self, serializer):
        obj = serializer.save()
        self._apply_effects(obj)

    @transaction.atomic
    def perform_update(self, serializer):
        obj = serializer.save()
        self._apply_effects(obj)


class GroupViewSet(viewsets.ModelViewSet):
    """
    /api/v1/groups/
      GET list/retrieve      — аутентифицированные
      POST/PUT/PATCH/DELETE  — staff/superuser ИЛИ пользователи с model perms

    Экшены:
      GET  /{id}/permissions
      POST /{id}/set-permissions
      POST /{id}/add-permissions
      POST /{id}/remove-permissions
    """

    queryset = Group.objects.all()
    serializer_class = GroupSerializer
    pagination_class = None

    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["name"]
    ordering_fields = ["name", "id"]
    ordering = ["name"]

    permission_classes = [IsAuthenticated, AdminOrActionOrModelPerms]
    required_perms_by_action = {
        "set_permissions": "employees.assign_group_permissions",
        "add_permissions": "employees.assign_group_permissions",
        "remove_permissions": "employees.assign_group_permissions",
    }

    # ----- helpers -----
    def _validate_permissions_payload(self, request):
        ids = request.data.get("permissions")
        if not isinstance(ids, list):
            return None, Response(
                {"detail": "Поле 'permissions' должно быть списком id"}, status=400
            )
        qs = Permission.objects.filter(id__in=ids)
        if qs.count() != len(set(ids)):
            return None, Response(
                {"detail": "Некоторые permissions не найдены"}, status=400
            )
        return qs, None

    # ----- actions -----
    @action(detail=True, methods=["get"])
    def permissions(self, request, pk=None):
        grp = self.get_object()
        perms = (
            Permission.objects.filter(group=grp)
            .select_related("content_type")
            .distinct()
        )
        data = [
            {
                "id": p.id,
                "codename": f"{p.content_type.app_label}.{p.codename}",
                "name": p.name,
                "app": p.content_type.app_label,
                "model": p.content_type.model,
            }
            for p in perms
        ]
        return Response({"count": len(data), "results": data}, status=200)

    @action(detail=True, methods=["post"])
    def set_permissions(self, request, pk=None):
        grp = self.get_object()
        qs, err = self._validate_permissions_payload(request)
        if err:
            return err
        grp.permissions.set(qs)
        return Response(
            {
                "ok": True,
                "permission_ids": list(grp.permissions.values_list("id", flat=True)),
            },
            status=200,
        )

    @action(detail=True, methods=["post"])
    def add_permissions(self, request, pk=None):
        grp = self.get_object()
        qs, err = self._validate_permissions_payload(request)
        if err:
            return err
        grp.permissions.add(*qs)
        return Response(
            {
                "ok": True,
                "permission_ids": list(grp.permissions.values_list("id", flat=True)),
            },
            status=200,
        )

    @action(detail=True, methods=["post"])
    def remove_permissions(self, request, pk=None):
        grp = self.get_object()
        qs, err = self._validate_permissions_payload(request)
        if err:
            return err
        grp.permissions.remove(*qs)
        return Response(
            {
                "ok": True,
                "permission_ids": list(grp.permissions.values_list("id", flat=True)),
            },
            status=200,
        )
