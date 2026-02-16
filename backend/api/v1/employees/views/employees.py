"""EmployeeViewSet — CRUD сотрудников, профиль, навыки, LDAP-info, Excel-экспорт."""

from __future__ import annotations

import logging
import traceback

from common.emails import send_templated_mail
from common.external_sync_mixin import ExternalSystemSyncMixin
from django.conf import settings
from django.core.files.base import ContentFile
from django.db import transaction
from django.db.models import Exists, OuterRef, Prefetch, Q, Subquery
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.crypto import get_random_string
from employees.constants import ACTION_DISMISSED
from employees.ldap.directory_service import DirectoryService, DirectoryUserDTO
from employees.ldap.errors import (DirectoryDbError, DirectoryLdapError,
                                   DirectoryServiceError)
from employees.ldap.infrastructure.connections import _conn
from employees.models import (Department, EmployeeAction, EmployeeDepartment,
                              LdapSyncState, Position, RoleAssignment, Skill)
from employees.utils import _to_bool
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from ...permissions import AdminOrActionOrModelPerms, IsSelfOrStaff
from ..serializers import (EmployeeListSerializer, EmployeeSerializer,
                           SkillSerializer)
from ._helpers import Employee, _is_ldap_enabled

logger = logging.getLogger(__name__)


class EmployeeViewSet(ExternalSystemSyncMixin, viewsets.ModelViewSet):
    """
    /api/v1/employees/

    Доступ:
      - GET list/retrieve          — только аутентифицированные пользователи.
      - POST (create)              — только staff/superuser.
      - PATCH/PUT/DELETE {id}      — staff/superuser ИЛИ пользователи с модельными правами.
      - GET/PATCH /employees/me/   — только аутентифицированные; PATCH правит профиль текущего пользователя.
      - POST {id}/add_skill|remove_skill — требуется employees.manage_employee_skills.

    Поиск: last_name, first_name, patronymic, email, phone_number

    Использует ExternalSystemSyncMixin для автоматической синхронизации с LDAP.
    """

    serializer_class = EmployeeSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["last_name", "first_name",
                     "patronymic", "email", "phone_number"]
    ordering_fields = ["last_name", "first_name", "created_at", "id"]
    ordering = ["last_name", "first_name"]
    required_perms_by_action = {
        "add_skill": "employees.manage_employee_skills",
        "remove_skill": "employees.manage_employee_skills",
        "ldap_info": "employees.view_ldap_info",
    }

    # ExternalSystemSyncMixin configuration
    external_sync_service = None  # Инициализируется в __init__ для каждого инстанса
    external_sync_enabled = True  # Можно отключить через settings или для тестов

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Создаем DirectoryService для каждого инстанса ViewSet
        if _is_ldap_enabled():
            self.external_sync_service = DirectoryService()
            self.external_sync_enabled = True
        else:
            self.external_sync_enabled = False

    def get_external_sync_method(self, action):
        """Маппинг ViewSet action -> метод DirectoryService."""
        if not _is_ldap_enabled():
            return None

        return {
            'create': 'create_user_in_ldap_only',
            'update': 'update_user_in_ldap_only',
            'partial_update': 'update_user_in_ldap_only',
            'destroy': 'delete_user_in_ldap_only',
        }.get(action)

    def prepare_external_data(self, instance, action):
        """Подготовка данных для передачи в LDAP сервис."""
        if action == 'create':
            # При создании передаем DTO с полными данными
            password = self.request.data.get('password')
            avatar_file = self.request.data.get('avatar')
            avatar_bytes = None
            
            if avatar_file and hasattr(avatar_file, 'read'):
                try:
                    if hasattr(avatar_file, 'seek'):
                        avatar_file.seek(0)
                    avatar_bytes = avatar_file.read()
                except Exception:
                    pass
            
            dto = DirectoryUserDTO(
                username=instance.username if instance.username else None,
                first_name=instance.first_name,
                last_name=instance.last_name,
                email=instance.email,
                phone_e164=str(instance.phone_number) if instance.phone_number else '',
                department_dn=self.request.data.get('department_dn'),
                group_cns=self.request.data.get('group_cns', []) or [],
                initial_password=password,
                avatar_bytes=avatar_bytes,
                is_active=instance.is_active,
            )
            return {'dto': dto, 'password': password}

        elif action in ['update', 'partial_update']:
            # При обновлении передаем инстанс и изменения
            return {
                'instance': instance,
                'changes': dict(self.request.data)
            }

        elif action == 'destroy':
            # При удалении передаем только инстанс
            return {'instance': instance}

        return {}

    def handle_external_sync_error(self, error, instance, action):
        """Обработка ошибок синхронизации с LDAP."""
        logger.error(
            f"LDAP sync failed for {action} on Employee {instance.id}: {error}",
            exc_info=True
        )

        # Возвращаем понятную ошибку пользователю
        if isinstance(error, (DirectoryLdapError, DirectoryServiceError)):
            return Response(
                {'detail': f'Ошибка синхронизации с LDAP: {str(error)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        # Для остальных ошибок - стандартная обработка
        return Response(
            {'detail': f'Ошибка внешней системы: {str(error)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
    
    def handle_external_sync_result(self, instance, result, action):
        """Обработка успешного результата синхронизации с LDAP.
        
        Вызывается миксином после успешной синхронизации.
        """
        if action != 'create' or not isinstance(result, dict):
            return
        
        dn = result.get('dn')
        guid = result.get('guid')
        
        if not dn:
            return
        
        # Сохраняем sync state
        st, _ = LdapSyncState.objects.get_or_create(
            model="employee", object_pk=str(instance.pk)
        )
        st.touch(
            ldap_dn=dn,
            ldap_guid=guid,
            sync_dir="ldap",
            last_django_modify_ts=timezone.now(),
        )
        
        # Записываем Django PK в LDAP employeeNumber для обратной связки
        try:
            from employees.ldap.infrastructure.connections import _ldap
            from employees.ldap.repositories.ldap_repository import modify_user_attrs
            
            employee_id_attr = getattr(settings, "LDAP_EMPLOYEE_ID_ATTR", "employeeNumber")
            with _ldap() as conn:
                modify_user_attrs(
                    conn, dn,
                    {employee_id_attr: str(instance.pk)},
                    do_write=True
                )
        except Exception as e:
            logger.warning(f"Failed to set employeeNumber in LDAP: {e}")
        
        # Назначаем должность если указана
        if instance.position_id:
            try:
                svc = self.external_sync_service or DirectoryService()
                svc.assign_position(instance, instance.position)
            except Exception as e:
                logger.warning(f"Failed to assign position in LDAP: {e}")

    def _perform_user_update(self, instance: Employee, request_data, is_partial=True):
        """Общая логика обновления пользователя для me PATCH и partial_update.

        Возвращает Response при ошибке или dict с 'data' и 'instance' при успехе.
        """
        old_email = instance.email

        # Удаляем пустое поле avatar
        data = request_data.copy() if hasattr(
            request_data, "copy") else dict(request_data)
        if hasattr(data, "_mutable") and not data._mutable:
            data._mutable = True
        avatar_raw = data.get("avatar")
        if avatar_raw in ("", None):
            data.pop("avatar", None)

        ser = self.get_serializer(instance, data=data, partial=is_partial)
        ser.is_valid(raise_exception=True)
        vd = dict(ser.validated_data)

        # Проверяем изменение email
        new_email = vd.get("email")
        email_changed = new_email and new_email.lower() != old_email.lower()

        ldap_enabled = _is_ldap_enabled()

        # --- LDAP часть ---
        ldap_keys = {
            "first_name",
            "last_name",
            "email",
            "phone_number",
            "is_active",
        }
        ldap_changes = {k: vd.pop(k)
                        for k in list(vd.keys()) if k in ldap_keys}

        svc_changes = dict(ldap_changes)
        pos_key_present = ("position" in data) or ("position_id" in data)
        if pos_key_present:
            pos_raw = (
                data.get("position") if "position" in data else data.get(
                    "position_id")
            )
            svc_changes["position"] = pos_raw
            vd.pop("position", None)
            vd.pop("position_id", None)

        move_to_department_dn = data.get("department_dn")
        group_cns = data.get("group_cns")

        # avatar → bytes
        avatar_file = ser.validated_data.get("avatar")
        if avatar_file and hasattr(avatar_file, "read"):
            try:
                svc_changes["avatar_bytes"] = avatar_file.read()
                if hasattr(avatar_file, "seek"):
                    avatar_file.seek(0)
            except Exception:
                pass

        # Проверяем, есть ли у пользователя ldap_dn
        has_ldap_dn = False
        if ldap_enabled:
            has_ldap_dn = LdapSyncState.objects.filter(
                model="employee", object_pk=str(instance.pk), ldap_dn__isnull=False
            ).exists() or (hasattr(instance, "ldap_dn") and instance.ldap_dn)

        if ldap_enabled and has_ldap_dn:
            svc = DirectoryService()
            if svc_changes or move_to_department_dn or group_cns is not None:
                try:
                    instance = svc.update_user(
                        instance,
                        changes=svc_changes,
                        group_cns=group_cns if group_cns is not None else None,
                        move_to_department_dn=move_to_department_dn,
                    )
                except (
                    DirectoryLdapError,
                    DirectoryDbError,
                    DirectoryServiceError,
                ) as e:
                    return Response(
                        {"detail": str(e)},
                        status=(502 if isinstance(
                            e, DirectoryLdapError) else 500),
                    )
        else:
            # Non-LDAP mode
            vd.update(ldap_changes)

            if pos_key_present:
                pos_raw = (
                    data.get("position")
                    if "position" in data
                    else data.get("position_id")
                )
                if pos_raw is None:
                    vd["position"] = None
                elif isinstance(pos_raw, int):
                    try:
                        vd["position"] = Position.objects.get(id=pos_raw)
                    except Position.DoesNotExist:
                        return Response(
                            {"detail": f"Position {pos_raw} not found"},
                            status=400,
                        )
                elif isinstance(pos_raw, dict) and "id" in pos_raw:
                    try:
                        vd["position"] = Position.objects.get(id=pos_raw["id"])
                    except Position.DoesNotExist:
                        return Response(
                            {"detail": f"Position {pos_raw['id']} not found"},
                            status=400,
                        )

            if avatar_file and hasattr(avatar_file, "read"):
                try:
                    if hasattr(avatar_file, "seek"):
                        avatar_file.seek(0)
                    avatar_bytes = avatar_file.read()
                    instance.avatar.save(
                        avatar_file.name,
                        ContentFile(avatar_bytes),
                        save=False,
                    )
                    vd.pop("avatar", None)
                except Exception:
                    pass

        # --- DB-only часть ---
        if "avatar" in vd:
            vd.pop("avatar")

        if vd:
            ser_db = self.get_serializer(instance, data=vd, partial=is_partial)
            try:
                ser_db.is_valid(raise_exception=True)
                ser_db.save()
                instance = ser_db.instance
                result_data = ser_db.data
            except ValidationError as exc:
                return Response(exc.detail, status=400)
        else:
            result_data = self.get_serializer(instance).data

        # Сброс email_verified при изменении email
        if email_changed:
            instance.email_verified = False
            instance.email_activation_code = get_random_string(6, "0123456789")
            instance.save(
                update_fields=["email_verified", "email_activation_code"])

            try:
                send_templated_mail(
                    subject="Подтверждение нового email",
                    to=[instance.email],
                    template_base="emails/registration_verify_code",
                    context={"code": instance.email_activation_code,
                             "user": instance},
                )
            except Exception:
                pass

            result_data["email_verified"] = False

        return {"data": result_data, "instance": instance}

    def get_permissions(self):
        if self.action == "create":
            return [IsAuthenticated(), AdminOrActionOrModelPerms()]
        if self.action in {
            "update",
            "partial_update",
            "destroy",
            "add_skill",
            "remove_skill",
            "ldap_info",
        }:
            return [IsAuthenticated(), (IsSelfOrStaff | AdminOrActionOrModelPerms)()]
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

        # по отделу
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
                head_ids = Department.objects.filter(
                    id=dep_id).values("head_id")
                role_assignment_ids = RoleAssignment.objects.filter(
                    role__department_id=dep_id, is_active=True
                ).values("employee_id")

                qs = qs.filter(
                    Q(id__in=member_ids)
                    | Q(id__in=head_ids)
                    | Q(id__in=role_assignment_ids)
                ).distinct()

                qs = qs.annotate(
                    _is_dept_member=Exists(
                        EmployeeDepartment.objects.filter(
                            employee_id=OuterRef("pk"),
                            department_id=dep_id,
                            is_active=True,
                        )
                    ),
                    _is_dept_head=Exists(
                        Department.objects.filter(
                            id=dep_id, head_id=OuterRef("pk"))
                    ),
                    _has_role_assignment=Exists(
                        RoleAssignment.objects.filter(
                            employee_id=OuterRef("pk"),
                            role__department_id=dep_id,
                            is_active=True,
                        )
                    ),
                )

                self.request._department_filter_id = dep_id

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

        created_at_gte = qp.get("created_at__gte")
        if created_at_gte:
            qs = qs.filter(created_at__gte=created_at_gte)

        return qs

    def get_serializer_class(self):
        if self.action == "list":
            return EmployeeListSerializer
        return EmployeeSerializer

    def create(self, request, *args, **kwargs):
        """Создание пользователя админом.
        
        Использует ExternalSystemSyncMixin для автоматической синхронизации с LDAP.
        Миксин управляет транзакциями и откатывает БД если LDAP упал.
        """
        if not (request.user.is_staff or request.user.is_superuser):
            return Response({"detail": "Only staff can create users."}, status=403)

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Валидация обязательных полей
        if not serializer.validated_data.get("email"):
            return Response({"detail": "email обязателен"}, status=400)
        if not serializer.validated_data.get("phone_number"):
            return Response({"detail": "phone_number обязателен"}, status=400)
        if not request.data.get("password"):
            return Response({"detail": "password обязателен"}, status=400)
        
        # Проверка контактов
        vd = serializer.validated_data
        if not (vd.get("whatsapp") or vd.get("telegram") or vd.get("wechat")):
            return Response(
                {"detail": "Заполните хотя бы одно из полей: WhatsApp, WeChat или Telegram"},
                status=400,
            )
        
        # Миксин автоматически вызовет perform_create() -> LDAP sync
        return super().create(request, *args, **kwargs)
    
    def perform_create(self, serializer):
        """Переопределяем для кастомной логики создания.
        
        ExternalSystemSyncMixin автоматически обернет это в транзакцию
        и вызовет LDAP синхронизацию после успешного сохранения.
        """
        password = self.request.data.get("password")
        avatar_bytes = None
        avatar_file = serializer.validated_data.get("avatar")
        
        if avatar_file and hasattr(avatar_file, "read"):
            try:
                avatar_bytes = avatar_file.read()
                if hasattr(avatar_file, "seek"):
                    avatar_file.seek(0)
            except Exception:
                pass
        
        ldap_enabled = _is_ldap_enabled()
        
        # Создаем пользователя в БД
        if ldap_enabled:
            # LDAP-managed пользователь с unusable password
            instance = serializer.save(is_ldap_managed=True)
            if hasattr(instance, "set_unusable_password"):
                instance.set_unusable_password()
                instance.save(update_fields=["password"])
        else:
            # Обычный пользователь с паролем в БД
            instance = serializer.save(is_ldap_managed=False)
            instance.set_password(password)
            instance.save(update_fields=["password"])
        
        # Сохраняем аватар если есть
        if avatar_bytes:
            instance.avatar.save(
                f"avatar_{instance.id}.jpg",
                ContentFile(avatar_bytes),
                save=False,
            )
            instance.save(update_fields=["avatar"])
        
        # Навыки
        skills_ids = self.request.data.get("skills_ids", [])
        if skills_ids:
            instance.skills.set(skills_ids)
        
        # Миксин вызовет LDAP синхронизацию автоматически после этого

    @action(detail=False, methods=["get", "patch"])
    def me(self, request):
        """GET — профиль текущего пользователя; PATCH — частичное обновление."""
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
            return Response(data, status=200)

        # PATCH — используем общий метод
        try:
            result = self._perform_user_update(
                instance, request.data, is_partial=True)
            if isinstance(result, Response):
                return result
            return Response(result["data"], status=200)
        except Exception as e:
            logger.error(f"[ME PATCH] FATAL ERROR: {e}", exc_info=True)
            return Response({"detail": f"Internal server error: {str(e)}"}, status=500)

    @action(detail=True, methods=["post"])
    def add_skill(self, request, pk=None):
        """body: { "skill_id": 3 } ИЛИ { "skill_name": "Python" }"""
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
        """body: { "skill_id": 3 } ИЛИ { "skill_name": "Python" }"""
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

    @action(detail=True, methods=["get"], url_path="ldap-info")
    def ldap_info(self, request, pk=None):
        """GET /api/v1/employees/{id}/ldap-info/ — LDAP информация о сотруднике."""
        from employees.ldap.repositories.ldap_repository import LdapRepository

        emp = self.get_object()
        force_refresh = request.query_params.get(
            'force_refresh', '').lower() == 'true'

        if not force_refresh and emp.username:
            return Response(
                {
                    "sAMAccountName": emp.username,
                    "cached": True,
                },
                status=status.HTTP_200_OK,
            )

        try:
            ldap_sync = LdapSyncState.objects.get(
                model='employee',
                object_pk=str(emp.pk)
            )
            if not ldap_sync.ldap_dn:
                return Response(
                    {"detail": "У этого сотрудника нет связи с LDAP"},
                    status=status.HTTP_404_NOT_FOUND,
                )
        except LdapSyncState.DoesNotExist:
            return Response(
                {"detail": "У этого сотрудника нет связи с LDAP"},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            conn = _conn()
            ldap_repo = LdapRepository(conn)
            attrs = ldap_repo.read_attrs(
                ldap_sync.ldap_dn,
                ["sAMAccountName"],
            )

            if not attrs or not attrs.get("sAMAccountName"):
                return Response(
                    {"detail": "Не удалось получить LDAP информацию"},
                    status=status.HTTP_404_NOT_FOUND,
                )

            sam_account_name = attrs.get("sAMAccountName")
            emp.username = sam_account_name
            emp.save(update_fields=["username"])

            return Response(
                {
                    "sAMAccountName": sam_account_name,
                    "cached": False,
                },
                status=status.HTTP_200_OK,
            )

        except Exception as e:
            logger.error(
                f"Error fetching LDAP info for employee {emp.id}: {e}", exc_info=True
            )
            return Response(
                {"detail": f"Ошибка при запросе LDAP информации: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=False, methods=["get"], url_path="export-excel")
    def export_excel(self, request):
        """GET /api/v1/employees/export-excel/ — экспорт в Excel."""
        from datetime import datetime

        from django.http import HttpResponse
        from openpyxl import Workbook
        from openpyxl.styles import Alignment, Font, PatternFill

        queryset = self.filter_queryset(self.get_queryset())
        queryset = (
            queryset.select_related("position")
            .prefetch_related(
                "skills", "departments_links__department", "departments_links__role"
            )
            .order_by("last_name", "first_name")
        )

        wb = Workbook()
        ws = wb.active
        ws.title = "Сотрудники"

        headers = [
            "ID",
            "Фамилия",
            "Имя",
            "Отчество",
            "Email",
            "Телефон",
            "Должность",
            "Отделы",
            "Дата рождения",
            "Дата регистрации",
            "Активен",
            "Email подтвержден",
            "Навыки",
            "Telegram",
            "WhatsApp",
            "WeChat",
        ]

        header_font = Font(bold=True, color="FFFFFF")
        header_fill = PatternFill(
            start_color="4472C4", end_color="4472C4", fill_type="solid"
        )
        header_alignment = Alignment(
            horizontal="center", vertical="center", wrap_text=True
        )

        for col_num, header in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col_num, value=header)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = header_alignment

        for row_num, emp in enumerate(queryset, 2):
            departments = emp.departments_links.filter(is_active=True)
            dept_names = ", ".join(
                [
                    f"{d.department.name}" +
                    (f" ({d.role.name})" if d.role else "")
                    for d in departments
                ]
            )

            skills = ", ".join([s.name for s in emp.skills.all()])

            def safe_phone_str(phone_field):
                """Безопасная конвертация PhoneNumber в строку"""
                if not phone_field:
                    return ""
                try:
                    from phonenumbers import PhoneNumberFormat, format_number

                    return format_number(phone_field, PhoneNumberFormat.INTERNATIONAL)
                except Exception:
                    try:
                        return str(phone_field)
                    except Exception:
                        return ""

            phone_str = safe_phone_str(emp.phone_number)
            whatsapp_str = safe_phone_str(emp.whatsapp)

            row_data = [
                emp.id,
                emp.last_name or "",
                emp.first_name or "",
                emp.patronymic or "",
                emp.email or "",
                phone_str,
                emp.position.name if emp.position else "",
                dept_names,
                emp.birth_date.strftime("%d.%m.%Y") if emp.birth_date else "",
                emp.created_at.strftime(
                    "%d.%m.%Y %H:%M") if emp.created_at else "",
                "Да" if emp.is_active else "Нет",
                "Да" if emp.email_verified else "Нет",
                skills,
                emp.telegram or "",
                whatsapp_str,
                emp.wechat or "",
            ]

            for col_num, value in enumerate(row_data, 1):
                cell = ws.cell(row=row_num, column=col_num, value=value)
                cell.alignment = Alignment(vertical="top", wrap_text=True)

        for col in ws.columns:
            max_length = 0
            column = col[0].column_letter
            for cell in col:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except Exception:
                    pass
            adjusted_width = min(max_length + 2, 50)
            ws.column_dimensions[column].width = adjusted_width

        ws.freeze_panes = "A2"

        response = HttpResponse(
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        filename = f"employees_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        response["Content-Disposition"] = f'attachment; filename="{filename}"'

        wb.save(response)
        return response

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        if getattr(self, "action", None) in {"retrieve", "me"}:
            ctx["include_actions"] = True
            ctx["include_action_history"] = True
        return ctx

    def partial_update(self, request, *args, **kwargs):
        """Частичное обновление: сначала LDAP-совместимые поля → затем DB-only."""
        emp = self.get_object()
        result = self._perform_user_update(emp, request.data, is_partial=True)
        if isinstance(result, Response):
            return result
        return Response(result["data"], status=200)
