"""GroupViewSet — CRUD и LDAP-операции с группами."""

from __future__ import annotations

from typing import Any, List, Optional

from django.conf import settings
from django.contrib.auth.models import Group, Permission
from django.core.exceptions import FieldError
from django.db import transaction
from django.db.models import OuterRef, Q, Subquery
from employees.ldap.directory_service import DirectoryService
from employees.models import LdapSyncState
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from ..permissions import AdminOrActionOrModelPerms
from ..serializers import GroupSerializer
from ._helpers import Employee, _is_ldap_enabled


class GroupViewSet(viewsets.ModelViewSet):
    """CRUD и LDAP-операции с группами.

    Базовые маршруты:
        GET/POST   /api/v1/groups/
        GET/PATCH/DELETE /api/v1/groups/{id}/

    Экшены: permissions, set-permissions, add-permissions, remove-permissions,
            rename, set-description, members, add-members, remove-members, replace-members
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
        "rename": "employees.assign_group_permissions",
        "set_description": "employees.assign_group_permissions",
        "add_members": "employees.assign_group_permissions",
        "remove_members": "employees.assign_group_permissions",
        "replace_members": "employees.assign_group_permissions",
    }

    # ---------- queryset ----------

    def get_queryset(self):
        qs = super().get_queryset()

        member_raw = self.request.query_params.get(
            "member"
        ) or self.request.query_params.get("member_id")
        if member_raw is None:
            return qs

        try:
            member_id = int(str(member_raw).strip())
        except (TypeError, ValueError):
            return qs.none()

        try:
            return qs.filter(
                Q(user__id=member_id) | Q(user_set__id=member_id)
            ).distinct()
        except FieldError:
            try:
                return qs.filter(user__id=member_id).distinct()
            except FieldError:
                try:
                    return qs.filter(user_set__id=member_id).distinct()
                except FieldError:
                    return qs.none()

    # ---------- helpers ----------

    def _validate_permissions_payload(
        self, request
    ) -> tuple[Optional[List[Permission]], Optional[Response]]:
        """Валидирует payload с ID permissions."""
        ids = request.data.get("permissions")
        if not isinstance(ids, list):
            return None, Response(
                {"detail": "Поле 'permissions' должно быть списком id"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            pid_list = [int(x) for x in ids]
        except (TypeError, ValueError):
            return None, Response(
                {"detail": "Список 'permissions' должен содержать целые числа"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        qs = Permission.objects.filter(id__in=pid_list)
        if qs.count() != len(set(pid_list)):
            return None, Response(
                {"detail": "Некоторые permissions не найдены"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return list(qs), None

    def _resolve_group_dn(self, grp: Group) -> Optional[str]:
        """Определяет DN группы по её CN."""
        if not _is_ldap_enabled():
            return None

        base = getattr(settings, "LDAP_GROUPS_BASE", "") or None
        svc = DirectoryService()
        try:
            return svc.group_find_dn(grp.name, bases=[base] if base else None)
        except AttributeError:
            return svc.find_group_dn(grp.name, bases=[base] if base else None)

    def _members_payload_to_dns(self, payload: dict[str, Any]) -> list[str]:
        """Извлекает список DN участников из payload (member_dns|member_ids)."""
        dns: list[str] = []
        raw_dns = payload.get("member_dns") or []
        if isinstance(raw_dns, list):
            dns.extend([d.strip() for d in raw_dns if isinstance(d, str) and d.strip()])

        ids = payload.get("member_ids") or []
        if isinstance(ids, list) and ids:
            if _is_ldap_enabled():
                svc = DirectoryService()
                dns.extend(
                    svc.employee_ids_to_dns([i for i in ids if isinstance(i, int)])
                )

        uniq, seen = [], set()
        for d in dns:
            if d and d not in seen:
                uniq.append(d)
                seen.add(d)

        if not _is_ldap_enabled():
            return []

        if not uniq:
            raise ValueError("Не переданы корректные member_dns или member_ids")
        return uniq

    def _dns_to_users(self, dns):
        """Маппит DN участников на локальных пользователей через LdapSyncState."""
        if not dns:
            return []

        sub = LdapSyncState.objects.filter(
            model="employee", object_pk=OuterRef("pk")
        ).values_list("ldap_dn", flat=True)[:1]

        return list(
            Employee.objects.annotate(ldap_dn=Subquery(sub))
            .filter(ldap_dn__in=dns)
            .only("id")
        )

    # ---------- override CRUD: LDAP → DB ----------

    def create(self, request, *args, **kwargs) -> Response:
        """Создаёт LDAP-группу, затем запись Group в БД."""
        ser = self.get_serializer(data=request.data)
        ser.is_valid(raise_exception=True)
        name: str = ser.validated_data["name"]

        parent_dn = request.data.get("ldap_parent_dn") or getattr(
            settings, "LDAP_GROUPS_BASE", None
        )
        description = request.data.get("ldap_description")
        scope = request.data.get("ldap_scope", "global")
        security_enabled = bool(request.data.get("ldap_security", True))

        ldap_enabled = _is_ldap_enabled()

        if ldap_enabled:
            svc = DirectoryService()
            try:
                svc.group_create(
                    cn=name,
                    parent_dn=parent_dn,
                    description=description,
                    scope=scope,
                    security_enabled=security_enabled,
                )
            except Exception as e:
                return Response({"detail": str(e)}, status=status.HTTP_502_BAD_GATEWAY)

        try:
            grp = Group.objects.create(name=name)
            perms = ser.validated_data.get("permissions")
            if perms:
                grp.permissions.set(perms)
        except Exception as e:
            if ldap_enabled:
                try:
                    svc = DirectoryService()
                    dn = None
                    try:
                        dn = svc.group_find_dn(
                            name, bases=[parent_dn] if parent_dn else None
                        )
                    except AttributeError:
                        dn = svc.find_group_dn(
                            name, bases=[parent_dn] if parent_dn else None
                        )
                    if dn:
                        svc.group_delete(dn)
                except Exception:
                    pass
            return Response(
                {"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        out = self.get_serializer(grp)
        return Response(
            out.data,
            status=status.HTTP_201_CREATED,
            headers=self.get_success_headers(out.data),
        )

    def partial_update(self, request, *args, **kwargs) -> Response:
        """Частичное обновление: сначала LDAP (rename/description), затем БД."""
        grp = self.get_object()
        new_name = request.data.get("name")
        new_desc = request.data.get("ldap_description", "__NO_CHANGE__")
        ldap_enabled = _is_ldap_enabled()

        if ldap_enabled:
            dn = self._resolve_group_dn(grp)
            if not dn:
                return Response(
                    {"detail": "Группа не найдена в LDAP"},
                    status=status.HTTP_404_NOT_FOUND,
                )

            svc = DirectoryService()
            try:
                if new_name and new_name != grp.name:
                    dn = svc.group_rename(dn, new_name)
                if new_desc != "__NO_CHANGE__":
                    svc.group_set_description(dn, (new_desc or None))
            except Exception as e:
                return Response({"detail": str(e)}, status=status.HTTP_502_BAD_GATEWAY)

        if new_name and new_name != grp.name:
            grp.name = new_name
            grp.save(update_fields=["name"])

        return super().partial_update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs) -> Response:
        """Удаляет LDAP-группу, затем запись Group в БД."""
        grp = self.get_object()
        force_db = str(request.query_params.get("force_db", "")).lower() in {
            "1",
            "true",
            "yes",
        }
        ldap_enabled = _is_ldap_enabled()

        if ldap_enabled:
            dn = self._resolve_group_dn(grp)
            if dn:
                try:
                    DirectoryService().group_delete(dn)
                except Exception as e:
                    if not force_db:
                        return Response(
                            {"detail": str(e)}, status=status.HTTP_502_BAD_GATEWAY
                        )

        return super().destroy(request, *args, **kwargs)

    def list(self, request, *args, **kwargs) -> Response:
        """Список групп. Перед выдачей — мягкий LDAP-синк каталога."""
        if _is_ldap_enabled():
            try:
                DirectoryService().sync_groups_catalog(throttle_seconds=60)
            except Exception:
                pass
        return super().list(request, *args, **kwargs)

    # ---------- Actions: Django permissions ----------

    @action(detail=True, methods=["get"])
    def permissions(self, request, pk=None) -> Response:
        """Permissions, привязанные к группе."""
        grp = self.get_object()
        perms = grp.permissions.select_related("content_type").distinct()
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
        return Response(
            {"count": len(data), "results": data}, status=status.HTTP_200_OK
        )

    @action(detail=True, methods=["post"], url_path="set-permissions")
    def set_permissions(self, request, pk=None) -> Response:
        """Полностью заменяет набор permissions у группы."""
        grp = self.get_object()
        qs, error = self._validate_permissions_payload(request)
        if error:
            return error
        grp.permissions.set(qs)
        return Response(
            {
                "ok": True,
                "permission_ids": list(grp.permissions.values_list("id", flat=True)),
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"], url_path="add-permissions")
    def add_permissions(self, request, pk=None) -> Response:
        """Добавляет permissions к группе."""
        grp = self.get_object()
        qs, error = self._validate_permissions_payload(request)
        if error:
            return error
        grp.permissions.add(*qs)
        return Response(
            {
                "ok": True,
                "permission_ids": list(grp.permissions.values_list("id", flat=True)),
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"], url_path="remove-permissions")
    def remove_permissions(self, request, pk=None) -> Response:
        """Удаляет указанные permissions у группы."""
        grp = self.get_object()
        qs, error = self._validate_permissions_payload(request)
        if error:
            return error
        grp.permissions.remove(*qs)
        return Response(
            {
                "ok": True,
                "permission_ids": list(grp.permissions.values_list("id", flat=True)),
            },
            status=status.HTTP_200_OK,
        )

    # ---------- Actions: LDAP ----------

    @action(detail=True, methods=["post"])
    def rename(self, request, pk=None) -> Response:
        """Переименовывает LDAP-группу и синхронизирует имя в БД."""
        grp = self.get_object()
        new_name = (request.data.get("new_name") or "").strip()
        if not new_name:
            return Response(
                {"detail": "new_name обязателен"}, status=status.HTTP_400_BAD_REQUEST
            )

        ldap_enabled = _is_ldap_enabled()

        if ldap_enabled:
            dn = self._resolve_group_dn(grp)
            if not dn:
                return Response(
                    {"detail": "Группа не найдена в LDAP"},
                    status=status.HTTP_404_NOT_FOUND,
                )

            svc = DirectoryService()
            try:
                svc.group_rename(dn, new_name)
            except Exception as e:
                return Response({"detail": str(e)}, status=status.HTTP_502_BAD_GATEWAY)

        grp.name = new_name
        grp.save(update_fields=["name"])
        return Response({"ok": True, "name": grp.name}, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="set-description")
    def set_description(self, request, pk=None) -> Response:
        """Устанавливает описание LDAP-группы."""
        grp = self.get_object()

        if not _is_ldap_enabled():
            return Response({"ok": True}, status=status.HTTP_200_OK)

        dn = self._resolve_group_dn(grp)
        if not dn:
            return Response(
                {"detail": "Группа не найдена в LDAP"}, status=status.HTTP_404_NOT_FOUND
            )

        svc = DirectoryService()
        try:
            svc.group_set_description(dn, request.data.get("description"))
            return Response({"ok": True}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"detail": str(e)}, status=status.HTTP_502_BAD_GATEWAY)

    @action(detail=True, methods=["get"])
    def members(self, request, pk=None) -> Response:
        """Состав LDAP-группы."""
        grp = self.get_object()

        if not _is_ldap_enabled():
            users = grp.user_set.all()
            employees = [
                {
                    "id": u.id,
                    "email": u.email,
                    "first_name": u.first_name,
                    "last_name": u.last_name,
                }
                for u in users
            ]
            return Response(
                {"dns": [], "employees": employees}, status=status.HTTP_200_OK
            )

        dn = self._resolve_group_dn(grp)
        if not dn:
            return Response(
                {"detail": "Группа не найдена в LDAP"}, status=status.HTTP_404_NOT_FOUND
            )

        svc = DirectoryService()
        try:
            dns = svc.group_list_members(dn)
        except Exception as e:
            return Response({"detail": str(e)}, status=status.HTTP_502_BAD_GATEWAY)

        employees = svc.employees_brief_by_dns(dns)
        return Response({"dns": dns, "employees": employees}, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="add-members")
    def add_members(self, request, pk=None) -> Response:
        """Добавляет участников в LDAP-группу и связывает в БД."""
        grp = self.get_object()
        ldap_enabled = _is_ldap_enabled()

        if ldap_enabled:
            dn = self._resolve_group_dn(grp)
            if not dn:
                return Response(
                    {"detail": "Группа не найдена в LDAP"},
                    status=status.HTTP_404_NOT_FOUND,
                )
            try:
                member_dns = self._members_payload_to_dns(request.data)
            except ValueError as e:
                return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

            svc = DirectoryService()
            try:
                svc.group_add_members(dn, member_dns)
            except Exception as e:
                return Response({"detail": str(e)}, status=status.HTTP_502_BAD_GATEWAY)

            users = self._dns_to_users(member_dns)
            ok_user_ids = [u.id for u in users]
            try:
                with transaction.atomic():
                    grp.user_set.add(*users)
            except Exception as e:
                try:
                    svc.group_remove_members(dn, member_dns)
                except Exception:
                    pass
                return Response(
                    {"detail": f"DB error: {e}"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

            return Response(
                {
                    "ok": True,
                    "ldap_added": len(member_dns),
                    "db_added": len(users),
                    "ok_dns": member_dns,
                    "ok_user_ids": ok_user_ids,
                },
                status=status.HTTP_200_OK,
            )
        else:
            member_ids = request.data.get("member_ids") or []
            if not isinstance(member_ids, list):
                return Response(
                    {"detail": "member_ids must be a list"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            users = Employee.objects.filter(id__in=member_ids)
            try:
                with transaction.atomic():
                    grp.user_set.add(*users)
            except Exception as e:
                return Response(
                    {"detail": f"DB error: {e}"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

            ok_user_ids = [u.id for u in users]
            return Response(
                {
                    "ok": True,
                    "ldap_added": 0,
                    "db_added": len(users),
                    "ok_dns": [],
                    "ok_user_ids": ok_user_ids,
                },
                status=status.HTTP_200_OK,
            )

    @action(detail=True, methods=["post"], url_path="remove-members")
    def remove_members(self, request, pk=None) -> Response:
        """Удаляет участников из LDAP-группы и разрывает связи в БД."""
        grp = self.get_object()
        ldap_enabled = _is_ldap_enabled()

        if ldap_enabled:
            dn = self._resolve_group_dn(grp)
            if not dn:
                return Response(
                    {"detail": "Группа не найдена в LDAP"},
                    status=status.HTTP_404_NOT_FOUND,
                )
            try:
                member_dns = self._members_payload_to_dns(request.data)
            except ValueError as e:
                return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

            svc = DirectoryService()
            try:
                svc.group_remove_members(dn, member_dns)
            except Exception as e:
                return Response({"detail": str(e)}, status=status.HTTP_502_BAD_GATEWAY)

            users = self._dns_to_users(member_dns)
            ok_user_ids = [u.id for u in users]
            try:
                with transaction.atomic():
                    grp.user_set.remove(*users)
            except Exception as e:
                try:
                    svc.group_add_members(dn, member_dns)
                except Exception:
                    pass
                return Response(
                    {"detail": f"DB error: {e}"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

            return Response(
                {
                    "ok": True,
                    "ldap_removed": len(member_dns),
                    "db_removed": len(users),
                    "ok_dns": member_dns,
                    "ok_user_ids": ok_user_ids,
                },
                status=status.HTTP_200_OK,
            )
        else:
            member_ids = request.data.get("member_ids") or []
            if not isinstance(member_ids, list):
                return Response(
                    {"detail": "member_ids must be a list"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            users = Employee.objects.filter(id__in=member_ids)
            try:
                with transaction.atomic():
                    grp.user_set.remove(*users)
            except Exception as e:
                return Response(
                    {"detail": f"DB error: {e}"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

            ok_user_ids = [u.id for u in users]
            return Response(
                {
                    "ok": True,
                    "ldap_removed": 0,
                    "db_removed": len(users),
                    "ok_dns": [],
                    "ok_user_ids": ok_user_ids,
                },
                status=status.HTTP_200_OK,
            )

    @action(detail=True, methods=["post"], url_path="replace-members")
    def replace_members(self, request, pk=None) -> Response:
        """Полностью заменяет состав LDAP-группы и синхронизирует M2M в БД."""
        grp = self.get_object()
        ldap_enabled = _is_ldap_enabled()

        if ldap_enabled:
            dn = self._resolve_group_dn(grp)
            if not dn:
                return Response(
                    {"detail": "Группа не найдена в LDAP"},
                    status=status.HTTP_404_NOT_FOUND,
                )
            try:
                desired_dns = self._members_payload_to_dns(request.data)
            except ValueError as e:
                return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

            svc = DirectoryService()
            try:
                prev_dns = svc.group_list_members(dn)
            except Exception as e:
                return Response({"detail": str(e)}, status=status.HTTP_502_BAD_GATEWAY)

            try:
                svc.group_replace_members(dn, desired_dns)
            except Exception as e:
                return Response({"detail": str(e)}, status=status.HTTP_502_BAD_GATEWAY)

            users = self._dns_to_users(desired_dns)
            ok_user_ids = [u.id for u in users]
            try:
                with transaction.atomic():
                    grp.user_set.set(users)
            except Exception as e:
                try:
                    svc.group_replace_members(dn, prev_dns)
                except Exception:
                    pass
                return Response(
                    {"detail": f"DB error: {e}"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

            return Response(
                {
                    "ok": True,
                    "ldap_total": len(desired_dns),
                    "db_total": len(users),
                    "ok_dns": desired_dns,
                    "ok_user_ids": ok_user_ids,
                },
                status=status.HTTP_200_OK,
            )
        else:
            member_ids = request.data.get("member_ids") or []
            if not isinstance(member_ids, list):
                return Response(
                    {"detail": "member_ids must be a list"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            users = Employee.objects.filter(id__in=member_ids)
            try:
                with transaction.atomic():
                    grp.user_set.set(users)
            except Exception as e:
                return Response(
                    {"detail": f"DB error: {e}"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

            ok_user_ids = [u.id for u in users]
            return Response(
                {
                    "ok": True,
                    "ldap_total": 0,
                    "db_total": len(users),
                    "ok_dns": [],
                    "ok_user_ids": ok_user_ids,
                },
                status=status.HTTP_200_OK,
            )
