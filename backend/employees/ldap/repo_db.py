from datetime import datetime
from typing import Dict, Iterable, Optional, Set, Tuple

from django.utils import timezone
from requests_app.enums import RequestStatus
from requests_app.models import Request

from ..models import Department, Employee, EmployeeDepartment, LdapSyncState
from .dto import LdapPersonDTO
from .utils import extract_department_from_dn


def _load_existing_users_index(
    dtos: Iterable[LdapPersonDTO],
) -> Tuple[Dict[str, Employee], Dict[str, Employee]]:
    """Строит индексы существующих пользователей по GUID и по e-mail (lower)."""
    guids: Set[str] = {d.guid.strip() for d in dtos if getattr(d, "guid", None)}
    emails_lower: Set[str] = {
        d.email.strip().lower() for d in dtos if getattr(d, "email", None)
    }

    by_email: Dict[str, Employee] = {}
    if emails_lower:
        # Берём ровно те email'ы, что пришли, и кладём ключами lower()
        qs = Employee.objects.filter(email__in=list(emails_lower)).only("id", "email")
        for u in qs:
            if u.email:
                by_email[u.email.lower()] = u

    # guid -> Employee через sync-state
    by_guid: Dict[str, Employee] = {}
    if guids:
        states = LdapSyncState.objects.filter(
            model="employee",
            ldap_guid__in=guids,
        ).values("ldap_guid", "object_pk")
        emp_map = {
            str(e.pk): e
            for e in Employee.objects.filter(
                pk__in={str(s["object_pk"]) for s in states}
            )
        }
        for s in states:
            emp = emp_map.get(str(s["object_pk"]))
            if emp:
                by_guid[str(s["ldap_guid"])] = emp

    return by_guid, by_email


def _find_user_for_dto(
    dto: LdapPersonDTO, *, by_guid: Dict[str, Employee], by_email: Dict[str, Employee]
) -> Optional[Employee]:
    """Находит пользователя по GUID, иначе по e-mail (lower)."""
    if dto.guid and dto.guid in by_guid:
        return by_guid[dto.guid]
    if dto.email:
        return by_email.get(dto.email.lower())
    return None


def _bind_user_department(user: Employee, dn: str) -> None:
    """Привязывает пользователя к отделу на основе DN (или снимает активную привязку).

    Args:
        user (Employee): Пользователь.
        dn (str): Distinguished Name пользователя.

    Raises:
        django.db.DatabaseError: Ошибки записи в БД.
    """
    dept_name = extract_department_from_dn(dn)
    if dept_name:
        dept_obj, _ = Department.objects.get_or_create(name=dept_name)
        EmployeeDepartment.objects.filter(employee=user, is_active=True).exclude(
            department=dept_obj
        ).update(is_active=False)
        link, made = EmployeeDepartment.objects.get_or_create(
            employee=user, department=dept_obj, defaults={"is_active": True}
        )
        if not made and not link.is_active:
            link.is_active = True
            link.save(update_fields=["is_active"])
    else:
        EmployeeDepartment.objects.filter(employee=user, is_active=True).update(
            is_active=False
        )


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
    """
    Обновляет/создаёт запись состояния синхронизации.
    """
    if dry_run:
        return

    state, _ = LdapSyncState.objects.get_or_create(
        model="employee", object_pk=str(user.pk)
    )
    state.touch(
        ldap_dn=dn,
        ldap_guid=guid or None,
        last_ldap_modify_ts=last_ldap_modify_ts,
        last_django_modify_ts=last_django_modify_ts or timezone.now(),
        sync_dir=sync_dir,
    )


def _cleanup_absent_users(
    *,
    seen_guids: Set[str],
    seen_dns: Set[str],
    dry_run: bool,
    show_changes: bool = False,
) -> int:
    """
    Обрабатывает сотрудников, отсутствующих в LDAP (зеркальный режим).
    Логика с «блокировкой» (approver с APPROVED/REJECTED) сохранена.
    """
    st_qs = LdapSyncState.objects.filter(model="employee")

    # Повторяем семантику прежнего .exclude(ldap_guid__in) и .exclude(ldap_dn__in)
    # но работаем по sync-state; дополнительно игнорируем пустые DN.
    stale_states = st_qs
    if seen_guids:
        stale_states = (
            stale_states.exclude(ldap_guid__in=seen_guids)
            .exclude(ldap_guid__isnull=True)
            .exclude(ldap_guid="")
        )
    if seen_dns:
        stale_states = stale_states.exclude(ldap_dn__in=seen_dns).exclude(ldap_dn="")

    emp_ids = list(stale_states.values_list("object_pk", flat=True))
    stale_qs = Employee.objects.filter(pk__in=emp_ids, is_ldap_managed=True)

    # Кто «заблокирован» из-за уже согласованных/отклонённых заявок
    blocked_ids_qs = (
        Request.objects.filter(
            approver__in=stale_qs.values("pk"),
            status__in=[RequestStatus.APPROVED, RequestStatus.REJECTED],
        )
        .values_list("approver_id", flat=True)
        .distinct()
    )
    blocked_qs = stale_qs.filter(pk__in=blocked_ids_qs)
    to_delete_qs = stale_qs.exclude(pk__in=blocked_ids_qs)

    if show_changes:
        blocked_emails = list(blocked_qs.values_list("email", flat=True))
        to_delete_emails = list(to_delete_qs.values_list("email", flat=True))
        for e in to_delete_emails:
            verb = "будет удалён" if dry_run else "удалён"
            print(f"[CHG] - User: {e} ({verb})")
        for e in blocked_emails:
            verb = "будет деактивирован" if dry_run else "деактивирован"
            print(f"[CHG] ! User: {e} ({verb}; есть утверждённые/отклонённые заявки)")

    blocked_count = blocked_qs.count()
    to_delete_count = to_delete_qs.count()

    print(
        f"[LDAP] Отсутствуют в каталоге: всего={stale_qs.count()}, "
        f"к удалению={to_delete_count}, к деактивации={blocked_count} (из-за заявлений APPROVED/REJECTED)"
    )

    if dry_run:
        return to_delete_count

    # 1) Деактивируем «заблокированных к удалению»
    if blocked_count:
        EmployeeDepartment.objects.filter(
            employee__in=blocked_qs.values("pk"), is_active=True
        ).update(is_active=False)
        Department.objects.filter(head__in=blocked_qs.values("pk")).update(head=None)
        blocked_qs.update(
            is_active=False,
            is_ldap_managed=False,
        )
        LdapSyncState.objects.filter(
            model="employee",
            object_pk__in=blocked_qs.values_list("pk", flat=True),
        ).delete()

    # 2) Удаляем остальных
    if to_delete_count:
        EmployeeDepartment.objects.filter(
            employee__in=to_delete_qs.values("pk")
        ).delete()
        Department.objects.filter(head__in=to_delete_qs.values("pk")).update(head=None)
        del_ids = list(to_delete_qs.values_list("pk", flat=True))
        to_delete_qs.delete()
        LdapSyncState.objects.filter(model="employee", object_pk__in=del_ids).delete()

    return to_delete_count
