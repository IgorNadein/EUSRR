# backend/api/v1/employees/views.py
from __future__ import annotations

from datetime import timedelta

from common.emails import send_templated_mail
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.db import IntegrityError, transaction
from django.db.models import (Case, Count, Exists, F, IntegerField, OuterRef,
                              Prefetch, Q, Subquery, Value, When)
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.crypto import get_random_string
from employees.constants import ACTION_DISMISSED
from employees.models import (Department, DepartmentPermission, DepartmentRole,
                              DeptPerm, EmployeeAction, EmployeeDepartment,
                              Position, Skill)
from integrations.ldap_writeback import update_employee_in_ldap  # наш сервис
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from ..permissions import (AdminOrActionOrModelPerms, AdminOrDeptAllowed,
                           IsSelfOrStaff, has_dept_perm)
from .serializers import (AddMemberInput, DepartmentBriefSerializer,
                          DepartmentRoleSerializer, DepartmentSerializer,
                          EmailSerializer, EmailVerifySerializer,
                          EmployeeActionSerializer, EmployeeBriefSerializer,
                          EmployeeListSerializer, EmployeeSerializer,
                          GroupSerializer, PositionSerializer,
                          RegisterSerializer, RemoveMemberInput, SetHeadInput,
                          SetMemberRoleInput, SkillSerializer)
from .utils import (_build_links_for_dept, _detect_phone_field,
                    _ensure_department_permissions, _head_choices_for_dept,
                    _normalize_phone, _perm_choices_synced, _to_bool,
                    _validate_head_active)

Employee = get_user_model()


PHONE_FIELD = _detect_phone_field()

_ME_ALLOWED_FIELDS = {
    "first_name", "last_name", "patronymic",
    "phone_number", "avatar",
    "telegram", "whatsapp", "wechat",
    "birth_date", "position_id",
}


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
    """Регистрация пользователя.

    Принимает JSON или multipart/form-data. Поле `avatar` можно передавать:
    - как файл (`multipart/form-data`);
    - как base64/data URI — если используете `Base64ImageField`.

    Важно: хотя бы одно из полей `telegram/whatsapp/wechat` должно быть заполнено.
    """

    throttle_scope = "anon"
    permission_classes = [AllowAny]
    parser_classes = (JSONParser, FormParser, MultiPartParser)

    @transaction.atomic
    def post(self, request):
        # 0) Хард-проверка контактов (как в тестах ожидается detail)
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
        if not phone_norm:
            return Response({"ok": False, "error": "invalid_phone"}, status=400)

        if Employee.objects.filter(phone_number=phone_norm).exists():
            return Response({"ok": False, "error": "phone_taken"}, status=400)

        user = Employee.objects.filter(email__iexact=email).first()
        if user and user.email_verified:
            return Response({"ok": False, "error": "email_taken"}, status=400)
        if user and not user.email_verified:
            return Response(
                {"ok": True, "pending_verification": True, "user_id": user.id},
                status=200,
            )

        extra = {
            "first_name": v["first_name"],
            "last_name": v["last_name"],
            "birth_date": v["birth_date"],
            "telegram": v.get("telegram", ""),
            "whatsapp": v.get("whatsapp", ""),
            "wechat": v.get("wechat", ""),
            # можно сразу пробросить, если ваш create_user это поддерживает:
            # "patronymic": v.get("patronymic") or "",
            # "gender": v.get("gender"),
        }

        try:
            user = Employee.objects.create_user(
                email=email,
                password=password,
                phone_number=phone_norm,
                **extra,
            )
        except IntegrityError as e:
            msg = str(e).lower()
            if "phone" in msg:
                return Response({"ok": False, "error": "phone_taken"}, status=400)
            if "email" in msg:
                return Response({"ok": False, "error": "email_taken"}, status=400)
            raise

        # 🔧 ВАЖНО: присвоить аватар и опциональные атрибуты
        avatar = v.get("avatar")
        if avatar:
            user.avatar = (
                avatar  # ImageField принимает InMemoryUploadedFile/ContentFile
            )
        if v.get("patronymic"):
            user.patronymic = v["patronymic"]
        if v.get("gender") is not None:
            user.gender = v["gender"]
        pos_id = v.get("position")
        if pos_id:
            user.position_id = (
                pos_id if Position.objects.filter(pk=pos_id).exists() else None
            )
        skills_ids = v.get("skills") or []
        if skills_ids:
            user.save()  # сохранить перед m2m
            user.skills.set(Skill.objects.filter(pk__in=skills_ids))
        user.save()

        return Response(
            {
                "id": user.id,
                "email": user.email,
                "email_verified": user.email_verified,
                "is_active": user.is_active,
                # при желании можно вернуть data URI (если хотите): "avatar": Base64ImageField().to_representation(user.avatar)
            },
            status=status.HTTP_201_CREATED,
        )


class DepartmentViewSet(viewsets.ModelViewSet):
    """
    CRUD отделов + действия:
      - POST /departments/{id}/set_head
      - POST /departments/{id}/set_member_role
      - POST /departments/{id}/add_member
      - POST /departments/{id}/remove_member
    Права:
      - update/partial_update/destroy → manage_department
      - set_head                   → change_department_head
      - set_member_role           → assign_department_role     (назначение/снятие роли)
      - add_member/remove_member  → manage_department          (управление участниками)
      - create                    → staff/superuser
      - чтение                    → аутентифицированным
    """

    queryset = Department.objects.select_related("head").prefetch_related("roles").all()
    serializer_class = DepartmentSerializer

    # пермишены (скоуп-право по отделу)
    class ManagePerm(AdminOrDeptAllowed):
        """Право на общее управление отделом."""

        required_code = DeptPerm.MANAGE

    class ChangeHeadPerm(AdminOrDeptAllowed):
        """Право на смену руководителя отдела."""

        required_code = DeptPerm.CHANGE_HEAD

    class AssignRolePerm(AdminOrDeptAllowed):
        """Право на назначение ролей участникам отдела."""

        required_code = DeptPerm.ASSIGN_ROLE

    def get_permissions(self):
        if self.action in {"update", "partial_update", "destroy"}:
            return [self.ManagePerm()]
        if self.action == "set_head":
            return [self.ChangeHeadPerm()]
        if self.action in {"set_member_role"}:
            return [self.AssignRolePerm()]
        if self.action in {"add_member", "remove_member"}:
            return [self.ManagePerm()]
        if self.action == "create":
            return [AdminOrActionOrModelPerms()]
        if self.action in {
            "members",
            "user_perms",
            "ui_context",
            "list",
            "retrieve",
            "my_departments",
        }:
            return [IsAuthenticated()]
        return [AdminOrActionOrModelPerms()]

    # --- поиск и сортировка, как в старой реализации/тестах ---
    ordering = ["name"]
    ordering_fields = ["name", "id"]

    def get_queryset(self):
        qs = super().get_queryset()

        # ---------- аннотации для employees_count ----------
        # Активные линкы данного отдела
        active_links = EmployeeDepartment.objects.filter(
            department_id=OuterRef("pk"), is_active=True
        )

        # Подсчёт distinct сотрудников по активным линкам
        active_count_subq = (
            active_links.values("department_id")
            .annotate(c=Count("employee_id", distinct=True))
            .values("c")[:1]
        )

        qs = qs.annotate(
            active_count=Coalesce(
                Subquery(active_count_subq, output_field=IntegerField()),
                Value(0),
            ),
            head_in_active=Exists(active_links.filter(employee_id=OuterRef("head_id"))),
        ).annotate(
            employees_count=F("active_count")
            + Case(
                When(
                    Q(head_id__isnull=False) & Q(head_in_active=False),
                    then=Value(1),
                ),
                default=Value(0),
                output_field=IntegerField(),
            )
        )
        # ---------- /аннотации ----------

        # Поиск и сортировка — как и раньше
        search = (
            self.request.query_params.get("search")
            or self.request.query_params.get("q")
            or ""
        ).strip()
        if search:
            qs = qs.filter(
                Q(name__icontains=search)
                | Q(description__icontains=search)
                | Q(head__first_name__icontains=search)
                | Q(head__last_name__icontains=search)
                | Q(head__patronymic__icontains=search)
            ).distinct()

        ordering = self.request.query_params.get("ordering")
        if ordering in {"name", "-name", "id", "-id"}:
            qs = qs.order_by(ordering)
        else:
            qs = qs.order_by("name")

        return qs

    # --- частичное изменение: изменение head требует отдельного кода ---

    def partial_update(self, request, *args, **kwargs):
        """
        Если меняется head, проверяем права и валидацию.
        Для действующего руководителя ослабляем требование email_verified.
        """
        instance = self.get_object()
        data = request.data

        wants_head_change = any(k in data for k in ("head", "head_id"))
        if wants_head_change:
            desired = data.get("head_id", data.get("head", None))
            if desired in ("", "null", "None"):
                desired = None

            current = instance.head_id if instance.head_id is not None else None
            desired_norm = int(desired) if desired is not None else None

            if current != desired_norm:
                perm = self.ChangeHeadPerm()
                if not (
                    perm.has_permission(request, self)
                    and perm.has_object_permission(request, self, instance)
                ):
                    return Response({"detail": "Forbidden"}, status=403)

                if desired_norm is None:
                    instance.head = None
                    instance.save(update_fields=["head"])
                else:
                    # ослабляем verified, если действие делает текущий head
                    require_verified = not (
                        instance.head_id and instance.head_id == request.user.id
                    )
                    ok, errs = _validate_head_active(
                        instance, desired_norm, require_email_verified=require_verified
                    )
                    if not ok:
                        return Response(errs, status=400)

                    instance.head_id = desired_norm
                    instance.save(update_fields=["head"])

            # подчистим поля
            mutable = getattr(request.data, "_mutable", None)
            try:
                if hasattr(request.data, "_mutable"):
                    request.data._mutable = True
                request.data.pop("head", None)
                request.data.pop("head_id", None)
            finally:
                if hasattr(request.data, "_mutable") and mutable is not None:
                    request.data._mutable = mutable

        return super().partial_update(request, *args, **kwargs)

    # -------- actions --------

    @action(detail=True, methods=["post"])
    @transaction.atomic
    def set_head(self, request, pk=None):
        """
        Назначение/снятие руководителя отдела.
        Текущий руководитель может назначить нового head без email_verified,
        если у кандидата is_active=True.
        """
        dept = self.get_object()
        payload = SetHeadInput(data=request.data)
        payload.is_valid(raise_exception=True)
        head_id = payload.validated_data.get("head_id")

        if head_id is None:
            dept.head = None
            dept.save(update_fields=["head"])
            return Response(status=status.HTTP_204_NO_CONTENT)

        # ослабляем требование verified, если действие делает текущий head
        require_verified = not (dept.head_id and dept.head_id == request.user.id)

        ok, errs = _validate_head_active(
            dept, head_id, require_email_verified=require_verified
        )
        if not ok:
            return Response(errs, status=400)

        dept.head_id = head_id
        dept.save(update_fields=["head"])
        return Response(self.get_serializer(dept).data, status=200)

    @action(detail=True, methods=["post"])
    @transaction.atomic
    def set_member_role(self, request, pk=None):
        """
        Назначает/снимает РОЛЬ существующему участнику отдела.
        Не создаёт членство и не меняет is_active.

        Тело:
            { "employee_id": <int>, "role_id": <int|null> }
        Права:
            AssignRolePerm (DeptPerm.ASSIGN_ROLE)
        Ответ:
            200 {"employee_id":..., "role_id": <int|null>, "is_active": <bool>}
            404 если сотрудник не состоит в отделе
            400 если роль не принадлежит отделу
        """
        dept = self.get_object()
        payload = SetMemberRoleInput(data=request.data)
        if not payload.is_valid():
            return Response(payload.errors, status=400)

        emp_id = payload.validated_data["employee_id"]
        role_id = payload.validated_data.get("role_id")

        # проверяем роль, если указана, что она принадлежит этому отделу
        role = None
        if role_id is not None:
            role = get_object_or_404(DepartmentRole, id=role_id)
            if role.department_id != dept.id:
                return Response(
                    {"role_id": ["Role does not belong to this department."]},
                    status=400,
                )

        # членство ДОЛЖНО существовать — не создаём автоматически
        try:
            link = EmployeeDepartment.objects.get(
                employee_id=emp_id, department_id=dept.id
            )
        except EmployeeDepartment.DoesNotExist:
            return Response(
                {"detail": "Employee is not a member of this department."}, status=404
            )

        # только меняем роль
        link.role = role
        link.save(update_fields=["role"])

        return Response(
            {
                "employee_id": emp_id,
                "role_id": (role.id if role else None),
                "is_active": link.is_active,
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["get"], url_path="members")
    def members(self, request, pk=None):
        """
        GET /api/v1/departments/{id}/members/
        Список участников отдела в формате, удобном для фронта-шаблона.
        """
        dept = self.get_object()
        links = _build_links_for_dept(dept, EmployeeBriefSerializer)
        return Response({"count": len(links), "results": links}, status=200)

    @action(detail=True, methods=["get"], url_path="user-perms")
    def user_perms(self, request, pk=None):
        """
        GET /api/v1/departments/{id}/user-perms/
        Флаги прав текущего пользователя в рамках отдела.
        """
        dept = self.get_object()
        uid = getattr(request.user, "id", None)
        data = {
            "is_head": bool(uid and uid == dept.head_id),
            "can_manage": has_dept_perm(request.user, dept.id, DeptPerm.MANAGE),
            "can_change_head": has_dept_perm(
                request.user, dept.id, DeptPerm.CHANGE_HEAD
            ),
            "can_assign_roles": has_dept_perm(
                request.user, dept.id, DeptPerm.ASSIGN_ROLE
            ),
        }
        return Response(data, status=200)

    @action(detail=True, methods=["get"], url_path="ui-context")
    def ui_context(self, request, pk=None):
        """
        GET /api/v1/departments/{id}/ui-context/
        BFF-агрегатор для страницы отдела: возвращает все необходимые данные одной пачкой.
        Поля:
          - dept: DepartmentSerializer
          - roles: DepartmentRoleSerializer[]
          - links: см. /members
          - head_choices: [{id,name}]
          - dept_perm_choices: [{id,code,name}]
          - user_perms: {is_head, can_manage, can_change_head, can_assign_roles}
        """
        dept = self.get_object()
        dept_data = self.get_serializer(dept).data

        roles_qs = (
            DepartmentRole.objects.filter(department_id=dept.id)
            .prefetch_related("scoped_permissions")
            .order_by("name", "id")
        )
        roles_data = DepartmentRoleSerializer(roles_qs, many=True).data

        links = _build_links_for_dept(dept, EmployeeBriefSerializer)
        perm_choices = _perm_choices_synced()
        head_choices = _head_choices_for_dept(dept, EmployeeBriefSerializer)
        user_perms = {
            "is_head": (
                request.user.id == dept.head_id
                if getattr(request.user, "id", None)
                else False
            ),
            "can_manage": has_dept_perm(request.user, dept.id, DeptPerm.MANAGE),
            "can_change_head": has_dept_perm(
                request.user, dept.id, DeptPerm.CHANGE_HEAD
            ),
            "can_assign_roles": has_dept_perm(
                request.user, dept.id, DeptPerm.ASSIGN_ROLE
            ),
        }

        payload = {
            "dept": dept_data,
            "roles": roles_data,
            "links": links,
            "head_choices": head_choices,
            "dept_perm_choices": perm_choices,
            "user_perms": user_perms,
        }
        return Response(payload, status=200)

    @action(detail=True, methods=["post"], url_path="add_member")
    @transaction.atomic
    def add_member(self, request, pk: int | None = None):
        """
        Активирует/добавляет сотрудника в отдел.
        Роль НЕ назначается здесь.

        Тело:
            { "employee_id": <int> }
        Права:
            ManagePerm (DeptPerm.MANAGE)

        Идемпотентно:
            если линк есть — делаем is_active=True, роль не трогаем.
        """
        dept = self.get_object()
        payload = AddMemberInput(data=request.data)
        payload.is_valid(raise_exception=True)

        emp_id = payload.validated_data["employee_id"]

        # проверим, что сотрудник существует (модель берём из FK на head)
        employee_model = Department._meta.get_field("head").remote_field.model
        get_object_or_404(employee_model, id=emp_id)

        link, _created = EmployeeDepartment.objects.get_or_create(
            employee_id=emp_id, department_id=dept.id, defaults={"is_active": True}
        )
        if not link.is_active:
            link.is_active = True
            link.save(update_fields=["is_active"])

        return Response(
            {
                "employee_id": emp_id,
                "is_active": True,
                "role_id": (link.role_id if getattr(link, "role_id", None) else None),
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"], url_path="remove_member")
    @transaction.atomic
    def remove_member(self, request, pk: int | None = None):
        """
        Удаляет связь сотрудника с отделом (строку EmployeeDepartment), а не просто
        помечает её неактивной.

        Тело запроса:
            { "employee_id": <int> }

        Ограничения:
            - Нельзя удалить руководителя отдела (вернёт 400).

        Права:
            ManagePerm (DeptPerm.MANAGE)

        Ответ:
            200 OK
            {
                "employee_id": <int>,
                "removed": true
            }
        """
        dept = self.get_object()

        payload = RemoveMemberInput(data=request.data)
        payload.is_valid(raise_exception=True)
        emp_id: int = payload.validated_data["employee_id"]

        # Защита от удаления руководителя
        if dept.head_id == emp_id:
            return Response(
                {"detail": "Нельзя удалить руководителя отдела."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        link = get_object_or_404(
            EmployeeDepartment,
            employee_id=emp_id,
            department_id=dept.id,
        )

        # Жёсткое удаление связи
        link.delete()

        return Response(
            {"employee_id": emp_id, "removed": True},
            status=status.HTTP_200_OK,
        )

    @action(detail=False, methods=["get"], url_path="my-departments")
    def my_departments(self, request) -> Response:
        """Вернёт список отделов, доступных текущему пользователю.

        Логика:
            Только отделы, где пользователь является руководителем
              или имеет активную связь в ``EmployeeDepartment`` (is_active=True).

        Args:
            request: Текущий HTTP-запрос DRF.

        Returns:
            Response: JSON-массив отделов в формате ``DepartmentSerializer`` (many=True),
            отсортированный по названию и id.

        Raises:
            NotAuthenticated: Если пользователь не авторизован (обрабатывается классом
                разрешений в ``get_permissions``).
        """
        user = request.user
        qs = self.get_queryset()

        active_link_exists = EmployeeDepartment.objects.filter(
            department_id=OuterRef("pk"),
            employee_id=user.id,
            is_active=True,
        )
        user_qs = qs.filter(Q(head_id=user.id) | Exists(active_link_exists)).distinct()

        user_qs = user_qs.order_by("name", "id")
        data = DepartmentBriefSerializer(user_qs, many=True).data
        return Response(data)


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
        
        if getattr(self, "action", None) in {"retrieve", "me"}:
            prefetches.append(Prefetch("actions", queryset=EmployeeAction.objects.order_by("-date")))

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

    def partial_update(self, request, *args, **kwargs):
        """Частичное обновление сотрудника с опциональным write-back в LDAP.

        Возвращает 409 при конфликте в каталоге (optimistic lock) и 503 при сетевых/LDAP-ошибках.
        """
        instance = self.get_object()

        # Валидацию делаем штатным сериализатором
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)

        # Пишем в LDAP, только если включено и есть whitelisted поля
        if update_employee_in_ldap and getattr(settings, "LDAP_WRITE_ENABLED", False):
            payload = {}
            # маппим нужные локальные поля → передадим сервису (он сам сопоставит к LDAP-атрибутам)
            for k in ("first_name", "last_name", "phone_number"):
                if k in serializer.validated_data:
                    payload[k] = serializer.validated_data[k]
            if payload:
                try:
                    update_employee_in_ldap(instance, payload=payload)
                except RuntimeError as e:
                    return Response({"detail": str(e)}, status=status.HTTP_409_CONFLICT)
                except Exception as e:
                    return Response({"detail": f"LDAP error: {e}"}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        # Локальное сохранение (включая прочие поля)
        self.perform_update(serializer)
        return Response(serializer.data, status=status.HTTP_200_OK)

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
        # 1) Явный allowlist: email менять только через отдельный процесс верификации
        safe_payload = {k: v for k, v in request.data.items() if k in _ME_ALLOWED_FIELDS}

        ser = self.get_serializer(instance, data=safe_payload, partial=True)
        ser.is_valid(raise_exception=True)

        # 2) Проверка канала связи (как и было)
        vd = ser.validated_data
        if all(k not in vd for k in ("whatsapp", "telegram", "wechat")):
            new_whatsapp = vd.get("whatsapp", instance.whatsapp)
            new_telegram = vd.get("telegram", instance.telegram)
            new_wechat = vd.get("wechat", instance.wechat)
            if not (new_whatsapp or new_telegram or new_wechat):
                return Response(
                    {"detail": "Должен быть указан хотя бы один канал связи (WhatsApp/Telegram/WeChat)."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        # 3) LDAP write-back: только whitelisted поля
        if update_employee_in_ldap and getattr(settings, "LDAP_WRITE_ENABLED", False):
            payload = {}
            for k in ("first_name", "last_name", "phone_number"):
                if k in ser.validated_data:
                    payload[k] = ser.validated_data[k]
            if payload:
                try:
                    update_employee_in_ldap(instance, payload=payload)
                except RuntimeError as e:
                    return Response({"detail": str(e)}, status=status.HTTP_409_CONFLICT)
                except Exception as e:
                    return Response({"detail": f"LDAP error: {e}"}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

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
    permission_classes = [AdminOrActionOrModelPerms]
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

    def get_permissions(self):
        """Возвращает пермишены для текущего экшена.

        Returns:
            list: Инスタнсы DRF-permission'ов.
        """
        if self.action in {"list", "retrieve", "permissions"}:
            return [IsAuthenticated()]
        if self.action == "create":
            return [AdminOrActionOrModelPerms()]
        return [AdminOrActionOrModelPerms()]

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
    Роли отдела:
      - list/retrieve с фильтром ?department=<id>
      - create/update/destroy → требуется право DeptPerm.ASSIGN_ROLE в рамках отдела роли
      - GET  /department-roles/perm_choices/
      - GET  /department-roles/{id}/perms/
      - POST /department-roles/{id}/set_perms  (ids или codes; полная замена)
    """

    queryset = (
        DepartmentRole.objects.select_related("department")
        .prefetch_related("scoped_permissions")
        .all()
    )
    serializer_class = DepartmentRoleSerializer

    class AssignRolePerm(AdminOrDeptAllowed):
        """Право на назначение ролей участникам отдела."""

        required_code = DeptPerm.ASSIGN_ROLE

    # стабильная сортировка для листинга
    ordering_fields = ("name", "id")
    ordering = ("name", "id")

    def get_permissions(self):
        if self.action in {
            "create",
            "update",
            "partial_update",
            "destroy",
            "set_perms",
        }:
            return [self.AssignRolePerm()]
        return [IsAuthenticated()]

    def get_queryset(self):
        """
        Фильтрация по отделу и стабильный порядок.
        """
        qs = super().get_queryset()
        dept = self.request.query_params.get("department")
        if dept:
            qs = qs.filter(department_id=dept)

        ord_param = self.request.query_params.get("ordering")
        if ord_param in {"name", "-name", "id", "-id"}:
            # стабильный тай-брейк по id
            qs = qs.order_by(
                ord_param, "id" if not ord_param.startswith("-") else "-id"
            )
        else:
            qs = qs.order_by(*self.ordering)
        return qs

    @action(detail=False, methods=["get"])
    def perm_choices(self, request):
        """
        Возвращает справочник скоуп-прав для ролей отдела из DeptPerm.CHOICES.
        Если каких-то записей нет в БД, создаёт их (идемпотентно).
        """
        data = _ensure_department_permissions()
        return Response({"count": len(data), "results": data}, status=200)

    @action(detail=True, methods=["get"])
    def perms(self, request, pk=None):
        """
        Возвращает список прав, назначенных данной роли (отсортирован по коду).
        """
        role = self.get_object()
        data = [
            {"id": p.id, "code": p.code, "name": p.name}
            for p in role.scoped_permissions.order_by("code")
        ]
        return Response({"count": len(data), "results": data}, status=200)

    @action(detail=True, methods=["post"])
    def set_perms(self, request, pk=None):
        """
        Полностью заменяет набор прав у роли.
        Тело запроса:
          - либо "permission_ids": [1,2,3]
          - либо "permission_codes": ["manage_department", ...]
        """
        role = self.get_object()

        ids = request.data.get("permission_ids") or []
        codes = request.data.get("permission_codes") or []

        if isinstance(ids, list) and ids:
            # валидация набора id
            ids_int = {int(i) for i in ids if str(i).isdigit()}
            qs = DepartmentPermission.objects.filter(id__in=ids_int)
            if qs.count() != len(ids_int):
                return Response(
                    {"detail": "Некоторые permission_ids не найдены."}, status=400
                )
        elif isinstance(codes, list) and codes:
            # валидация набора кодов
            codes_set = set(codes)
            qs = DepartmentPermission.objects.filter(code__in=codes_set)
            if qs.count() != len(codes_set):
                return Response(
                    {"detail": "Некоторые permission_codes не найдены."}, status=400
                )
        else:
            qs = DepartmentPermission.objects.none()

        role.scoped_permissions.set(list(qs))
        ser = self.get_serializer(role)
        return Response(ser.data, status=200)


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
        if self.action in ("create", "bulk_create", "list", "retrieve"):
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
