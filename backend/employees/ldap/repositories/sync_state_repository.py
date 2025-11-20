"""Репозиторий для работы с состоянием синхронизации LDAP.

Управляет записями LdapSyncState, которые отслеживают соответствие между
объектами Django и LDAP (DN, GUID, временные метки).
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from django.db.models import QuerySet
from django.utils import timezone

from employees.models import Employee, LdapSyncState


class SyncStateRepository:
    """Репозиторий для работы с LdapSyncState.
    
    Предоставляет методы для создания, обновления и поиска состояний
    синхронизации объектов между Django и LDAP.
    """

    @staticmethod
    def get_or_create(
        model: str, object_pk: str
    ) -> tuple[LdapSyncState, bool]:
        """Получить или создать запись состояния синхронизации.

        Args:
            model: Тип модели ('employee', 'department').
            object_pk: PK объекта в Django.

        Returns:
            Кортеж (state, created).
        """
        return LdapSyncState.objects.get_or_create(
            model=model, object_pk=str(object_pk)
        )

    @staticmethod
    def get_state(model: str, object_pk: str) -> Optional[LdapSyncState]:
        """Получить состояние синхронизации или None.

        Args:
            model: Тип модели ('employee', 'department').
            object_pk: PK объекта в Django.

        Returns:
            LdapSyncState или None, если не найдено.
        """
        try:
            return LdapSyncState.objects.get(
                model=model, object_pk=str(object_pk)
            )
        except LdapSyncState.DoesNotExist:
            return None

    @staticmethod
    def touch(
        emp: Employee,
        *,
        dn: str,
        guid: Optional[str] = None,
        last_ldap_modify_ts: Optional[datetime] = None,
        last_django_modify_ts: Optional[datetime] = None,
        sync_dir: str = "ldap",
        dry_run: bool = False,
    ) -> None:
        """Обновить/создать запись состояния синхронизации для сотрудника.

        Args:
            emp: Объект сотрудника.
            dn: Distinguished Name в LDAP.
            guid: GUID объекта в LDAP.
            last_ldap_modify_ts: Время последнего изменения в LDAP.
            last_django_modify_ts: Время последнего изменения в Django.
            sync_dir: Направление синхронизации ('ldap' или 'django').
            dry_run: Если True, не выполнять изменения.
        """
        if dry_run:
            return

        state, _ = LdapSyncState.objects.get_or_create(
            model="employee", object_pk=str(emp.pk)
        )
        state.touch(
            ldap_dn=dn,
            ldap_guid=guid or None,
            last_ldap_modify_ts=last_ldap_modify_ts,
            last_django_modify_ts=last_django_modify_ts or timezone.now(),
            sync_dir=sync_dir,
        )

    @staticmethod
    def get_employees_with_dn() -> QuerySet[Employee]:
        """Получить всех сотрудников с заполненным DN в sync-state.

        Returns:
            QuerySet сотрудников.
        """
        emp_ids = (
            LdapSyncState.objects.filter(model="employee")
            .exclude(ldap_dn="")
            .values_list("object_pk", flat=True)
        )
        return Employee.objects.filter(pk__in=list(emp_ids)).select_related()

    @staticmethod
    def delete_for_employee(emp_pk: int | str) -> None:
        """Удалить состояние синхронизации для сотрудника.

        Args:
            emp_pk: PK сотрудника.
        """
        LdapSyncState.objects.filter(
            model="employee", object_pk=str(emp_pk)
        ).delete()

    @staticmethod
    def bulk_delete_for_employees(emp_pks: list[int | str]) -> None:
        """Удалить состояния синхронизации для нескольких сотрудников.

        Args:
            emp_pks: Список PK сотрудников.
        """
        str_pks = [str(pk) for pk in emp_pks]
        LdapSyncState.objects.filter(
            model="employee", object_pk__in=str_pks
        ).delete()


# Функция для обратной совместимости
def _touch_sync_state(
    user: Employee,
    *,
    dn: str,
    guid: Optional[str],
    last_ldap_modify_ts: Optional[datetime] = None,
    last_django_modify_ts: Optional[datetime] = None,
    sync_dir: str = "ldap",
    dry_run: bool = False,
) -> None:
    """Обратная совместимость. Использует SyncStateRepository."""
    SyncStateRepository.touch(
        user,
        dn=dn,
        guid=guid,
        last_ldap_modify_ts=last_ldap_modify_ts,
        last_django_modify_ts=last_django_modify_ts,
        sync_dir=sync_dir,
        dry_run=dry_run,
    )


__all__ = [
    "SyncStateRepository",
    "_touch_sync_state",  # Обратная совместимость
]
