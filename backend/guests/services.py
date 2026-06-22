from __future__ import annotations

import logging
from datetime import datetime, time, timedelta
from typing import Iterable

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from communications import comments_helpers
from communications.models import ChatReadState
from employees.models import LdapSyncQueue, LdapSyncState
from guests.ldap.orm_models import GuestEmployeeNumberConflict, LdapGuestUser
from notifications.signals import notify

from .constants import GuestVisitEventType, GuestVisitStatus
from .models import Guest, GuestVisit, GuestVisitEvent
from .permissions import GUEST_ADMIN_PERMS

logger = logging.getLogger(__name__)
User = get_user_model()


def get_guest_admin_users():
    return (
        User.objects.filter(
            Q(is_staff=True)
            | Q(is_superuser=True)
            | Q(user_permissions__codename__in=[p.split(".")[1] for p in GUEST_ADMIN_PERMS])
            | Q(groups__permissions__codename__in=[p.split(".")[1] for p in GUEST_ADMIN_PERMS])
        )
        .filter(is_active=True)
        .distinct()
    )


def record_guest_event(
    visit: GuestVisit,
    event_type: str,
    *,
    actor=None,
    from_status: str = "",
    to_status: str = "",
    comment: str = "",
    metadata: dict | None = None,
) -> GuestVisitEvent:
    return GuestVisitEvent.objects.create(
        visit=visit,
        actor=actor if actor and getattr(actor, "is_authenticated", False) else None,
        event_type=event_type,
        from_status=from_status or "",
        to_status=to_status or "",
        comment=comment or "",
        metadata=metadata or {},
    )


def notify_guest_visit(
    visit: GuestVisit,
    verb: str,
    recipients: Iterable,
    *,
    actor=None,
    title: str,
    message: str,
    extra: dict | None = None,
) -> None:
    recipient_list = [u for u in recipients if u and getattr(u, "is_active", False)]
    if not recipient_list:
        return
    notify.send(
        sender=actor or visit.inviter,
        recipient=recipient_list,
        verb=verb,
        action_object=visit,
        target=visit.guest,
        description=message,
        action_url=f"/guests?visit={visit.pk}",
        data={
            "title": title,
            "visit_id": visit.pk,
            "guest_id": str(visit.guest_id),
            "guest_name": visit.guest.full_name,
            **(extra or {}),
        },
    )


def resolve_inviter_department(inviter):
    departments = getattr(inviter, "departments", None)
    try:
        return departments.first() if departments is not None else None
    except Exception:
        return None


def normalize_all_day_range(date_from, date_to):
    tz = timezone.get_current_timezone()
    starts_at = timezone.make_aware(datetime.combine(date_from, time.min), tz)
    expires_at = timezone.make_aware(
        datetime.combine(date_to + timedelta(days=1), time.min),
        tz,
    )
    return starts_at, expires_at


GUEST_VISIT_PERIOD_BLOCKING_STATUSES = {
    GuestVisitStatus.PENDING,
    GuestVisitStatus.NEEDS_INFO,
    GuestVisitStatus.APPROVED,
}


def get_overlapping_guest_visit(
    *,
    guest: Guest,
    starts_at,
    expires_at,
    unlimited: bool,
    exclude_pk: int | None = None,
) -> GuestVisit | None:
    qs = GuestVisit.objects.filter(
        guest=guest,
        status__in=GUEST_VISIT_PERIOD_BLOCKING_STATUSES,
    )
    if exclude_pk:
        qs = qs.exclude(pk=exclude_pk)

    if unlimited:
        return qs.order_by("-created_at").first()

    if not starts_at or not expires_at:
        return None

    return (
        qs.filter(
            Q(unlimited=True)
            | (
                (
                    Q(access_starts_at__isnull=True)
                    | Q(access_starts_at__lt=expires_at)
                )
                & (
                    Q(access_expires_at__isnull=True)
                    | Q(access_expires_at__gt=starts_at)
                )
            )
        )
        .order_by("-created_at")
        .first()
    )


def validate_guest_visit_period_available(
    *,
    guest: Guest,
    starts_at,
    expires_at,
    unlimited: bool,
    exclude_pk: int | None = None,
) -> None:
    if get_overlapping_guest_visit(
        guest=guest,
        starts_at=starts_at,
        expires_at=expires_at,
        unlimited=unlimited,
        exclude_pk=exclude_pk,
    ):
        raise ValueError(
            "У этого гостя уже есть заявка с пересекающимся периодом доступа."
        )


def validate_guest_visit_period_not_past(
    *,
    expires_at,
    unlimited: bool,
) -> None:
    if unlimited:
        return
    if expires_at and expires_at <= timezone.now():
        raise ValueError(
            "Нельзя создать заявку с периодом доступа, который уже истек."
        )


def has_unread_info_response_for_user(visit: GuestVisit, user) -> bool:
    if not user or not getattr(user, "is_authenticated", False):
        return False

    chat = comments_helpers.get_comments_chat_if_exists(visit)
    if not chat:
        return False

    latest_request = (
        chat.messages.filter(
            author=user,
            is_deleted=False,
            system_metadata__guest_visit_comment_type="info_request",
        )
        .order_by("-created_at", "-id")
        .first()
    )
    if not latest_request:
        return False

    latest_response = (
        chat.messages.filter(
            is_deleted=False,
            created_at__gt=latest_request.created_at,
            system_metadata__guest_visit_comment_type="info_response",
        )
        .exclude(author=user)
        .order_by("-created_at", "-id")
        .first()
    )
    if not latest_response:
        return False

    read_state = ChatReadState.objects.filter(chat=chat, user=user).first()
    return not (
        read_state
        and read_state.last_read_message_id
        and read_state.last_read_message_id >= latest_response.id
    )


class GuestVisitWorkflow:
    @staticmethod
    def _inviter_is_active(visit: GuestVisit) -> bool:
        inviter = visit.inviter
        return bool(inviter.is_active and getattr(inviter, "is_actually_active", True))

    @staticmethod
    def create_visit(*, actor, guest: Guest, **data) -> GuestVisit:
        with transaction.atomic():
            guest = Guest.objects.select_for_update().get(pk=guest.pk)
            validate_guest_visit_period_available(
                guest=guest,
                starts_at=data.get("access_starts_at"),
                expires_at=data.get("access_expires_at"),
                unlimited=bool(data.get("unlimited", False)),
            )
            validate_guest_visit_period_not_past(
                expires_at=data.get("access_expires_at"),
                unlimited=bool(data.get("unlimited", False)),
            )
            department = resolve_inviter_department(actor)
            visit = GuestVisit.objects.create(
                guest=guest,
                inviter=actor,
                inviter_snapshot_name=(actor.get_full_name() or str(actor)),
                inviter_snapshot_email=getattr(actor, "email", "") or "",
                host_department=department,
                status=GuestVisitStatus.PENDING,
                submitted_at=timezone.now(),
                **data,
            )
            record_guest_event(
                visit,
                GuestVisitEventType.CREATED,
                actor=actor,
                to_status=visit.status,
            )
            record_guest_event(
                visit,
                GuestVisitEventType.SUBMITTED,
                actor=actor,
                to_status=visit.status,
            )
            notify_guest_visit(
                visit,
                "guest_visit_submitted",
                get_guest_admin_users(),
                actor=actor,
                title="Гостевой визит на рассмотрении",
                message=f"{actor} создал гостевой визит для {visit.guest.full_name}.",
            )
            return visit

    @staticmethod
    def _set_status(
        visit: GuestVisit,
        new_status: str,
        *,
        actor,
        event_type: str,
        comment: str = "",
        update_fields: list[str] | None = None,
    ) -> GuestVisit:
        old_status = visit.status
        visit.status = new_status
        fields = ["status", "updated_at", *(update_fields or [])]
        visit.save(update_fields=fields)
        record_guest_event(
            visit,
            event_type,
            actor=actor,
            from_status=old_status,
            to_status=new_status,
            comment=comment,
        )
        return visit

    @classmethod
    def submit(cls, visit: GuestVisit, *, actor) -> GuestVisit:
        if visit.status == GuestVisitStatus.PENDING:
            return visit
        if visit.status not in {GuestVisitStatus.DRAFT, GuestVisitStatus.NEEDS_INFO}:
            raise ValueError("Отправить можно только черновик или заявку с уточнениями.")
        if not visit.purpose.strip():
            raise ValueError("Укажите цель приглашения.")
        if not visit.unlimited and not (visit.access_starts_at and visit.access_expires_at):
            raise ValueError("Укажите период доступа или бессрочный доступ.")
        if (
            getattr(settings, "GUESTS_REQUIRE_ID_DOCUMENT", False)
            and not visit.documents.exists()
        ):
            raise ValueError("Прикрепите документ гостя.")
        validate_guest_visit_period_available(
            guest=visit.guest,
            starts_at=visit.access_starts_at,
            expires_at=visit.access_expires_at,
            unlimited=visit.unlimited,
            exclude_pk=visit.pk,
        )
        validate_guest_visit_period_not_past(
            expires_at=visit.access_expires_at,
            unlimited=visit.unlimited,
        )
        visit.submitted_at = timezone.now()
        event = (
            GuestVisitEventType.INFO_PROVIDED
            if visit.status == GuestVisitStatus.NEEDS_INFO
            else GuestVisitEventType.SUBMITTED
        )
        cls._set_status(
            visit,
            GuestVisitStatus.PENDING,
            actor=actor,
            event_type=event,
            update_fields=["submitted_at"],
        )
        notify_guest_visit(
            visit,
            "guest_visit_submitted" if event == GuestVisitEventType.SUBMITTED else "guest_visit_info_provided",
            get_guest_admin_users(),
            actor=actor,
            title="Гостевой визит на рассмотрении",
            message=f"{actor} отправил гостевой визит для {visit.guest.full_name}.",
        )
        return visit

    @classmethod
    def request_info(cls, visit: GuestVisit, *, actor, comment: str) -> GuestVisit:
        if visit.status != GuestVisitStatus.PENDING:
            raise ValueError("Запросить уточнения можно только по заявке на рассмотрении.")
        comment = comment.strip()
        if not comment:
            raise ValueError("Комментарий обязателен.")
        comments_helpers.create_comment(
            visit,
            actor,
            comment,
            guest_visit_comment_type="info_request",
        )
        cls._set_status(
            visit,
            GuestVisitStatus.NEEDS_INFO,
            actor=actor,
            event_type=GuestVisitEventType.NEEDS_INFO_REQUESTED,
            comment=comment,
        )
        notify_guest_visit(
            visit,
            "guest_visit_needs_info",
            [visit.inviter],
            actor=actor,
            title="Нужна информация по гостевому визиту",
            message=comment,
        )
        return visit

    @classmethod
    def approve(cls, visit: GuestVisit, *, actor, comment: str = "") -> GuestVisit:
        if visit.status not in {GuestVisitStatus.PENDING, GuestVisitStatus.REJECTED}:
            raise ValueError("Одобрить можно только заявку на рассмотрении или отклоненную заявку.")
        if visit.inviter_inactive or not cls._inviter_is_active(visit):
            raise ValueError("Нельзя одобрить заявку с неактивным приглашающим.")
        validate_guest_visit_period_available(
            guest=visit.guest,
            starts_at=visit.access_starts_at,
            expires_at=visit.access_expires_at,
            unlimited=visit.unlimited,
            exclude_pk=visit.pk,
        )
        validate_guest_visit_period_not_past(
            expires_at=visit.access_expires_at,
            unlimited=visit.unlimited,
        )
        old_status = visit.status
        visit.decided_by = actor
        visit.decided_at = timezone.now()
        visit.decision_comment = comment
        event_type = (
            GuestVisitEventType.DECISION_CHANGED
            if old_status == GuestVisitStatus.REJECTED
            else GuestVisitEventType.APPROVED
        )
        cls._set_status(
            visit,
            GuestVisitStatus.APPROVED,
            actor=actor,
            event_type=event_type,
            comment=comment,
            update_fields=["decided_by", "decided_at", "decision_comment"],
        )
        notify_guest_visit(
            visit,
            "guest_visit_approved",
            [visit.inviter],
            actor=actor,
            title="Гостевой визит одобрен",
            message=f"Гостевой визит для {visit.guest.full_name} одобрен.",
        )
        GuestLdapService().sync_guest_for_visit(visit)
        return visit

    @classmethod
    def reject(cls, visit: GuestVisit, *, actor, comment: str = "") -> GuestVisit:
        if visit.status not in {
            GuestVisitStatus.PENDING,
            GuestVisitStatus.NEEDS_INFO,
            GuestVisitStatus.APPROVED,
        }:
            raise ValueError("Отклонить можно только рассматриваемую или одобренную заявку.")
        old_status = visit.status
        visit.decided_by = actor
        visit.decided_at = timezone.now()
        visit.decision_comment = comment
        event_type = (
            GuestVisitEventType.DECISION_CHANGED
            if old_status == GuestVisitStatus.APPROVED
            else GuestVisitEventType.REJECTED
        )
        cls._set_status(
            visit,
            GuestVisitStatus.REJECTED,
            actor=actor,
            event_type=event_type,
            comment=comment,
            update_fields=["decided_by", "decided_at", "decision_comment"],
        )
        notify_guest_visit(
            visit,
            "guest_visit_rejected",
            [visit.inviter],
            actor=actor,
            title="Гостевой визит отклонен",
            message=f"Гостевой визит для {visit.guest.full_name} отклонен.",
        )
        GuestLdapService().disable_guest(visit.guest, visit=visit)
        return visit

    @classmethod
    def cancel(cls, visit: GuestVisit, *, actor, comment: str = "") -> GuestVisit:
        if visit.status not in {
            GuestVisitStatus.DRAFT,
            GuestVisitStatus.PENDING,
            GuestVisitStatus.NEEDS_INFO,
            GuestVisitStatus.APPROVED,
        }:
            raise ValueError("Отменить можно только активную заявку.")
        visit.cancelled_by = actor
        visit.cancelled_at = timezone.now()
        visit.cancel_reason = comment
        cls._set_status(
            visit,
            GuestVisitStatus.CANCELLED,
            actor=actor,
            event_type=GuestVisitEventType.CANCELLED,
            comment=comment,
            update_fields=["cancelled_by", "cancelled_at", "cancel_reason"],
        )
        GuestLdapService().disable_guest_if_no_active_visits(visit.guest, visit=visit)
        return visit

    @classmethod
    def return_to_work(
        cls,
        visit: GuestVisit,
        *,
        actor,
        comment: str = "",
    ) -> GuestVisit:
        if visit.status not in {
            GuestVisitStatus.CANCELLED,
            GuestVisitStatus.REVOKED,
            GuestVisitStatus.EXPIRED,
        }:
            raise ValueError("Вернуть в работу можно только закрытую заявку.")
        if visit.inviter_inactive or not cls._inviter_is_active(visit):
            raise ValueError("Нельзя вернуть в работу заявку с неактивным приглашающим.")
        validate_guest_visit_period_available(
            guest=visit.guest,
            starts_at=visit.access_starts_at,
            expires_at=visit.access_expires_at,
            unlimited=visit.unlimited,
            exclude_pk=visit.pk,
        )
        validate_guest_visit_period_not_past(
            expires_at=visit.access_expires_at,
            unlimited=visit.unlimited,
        )
        old_status = visit.status
        visit.status = GuestVisitStatus.PENDING
        visit.submitted_at = timezone.now()
        visit.decided_by = None
        visit.decided_at = None
        visit.decision_comment = ""
        visit.cancelled_by = None
        visit.cancelled_at = None
        visit.cancel_reason = ""
        visit.revoked_by = None
        visit.revoked_at = None
        visit.revoke_reason = ""
        visit.expired_at = None
        visit.save(
            update_fields=[
                "status",
                "submitted_at",
                "decided_by",
                "decided_at",
                "decision_comment",
                "cancelled_by",
                "cancelled_at",
                "cancel_reason",
                "revoked_by",
                "revoked_at",
                "revoke_reason",
                "expired_at",
                "updated_at",
            ]
        )
        record_guest_event(
            visit,
            GuestVisitEventType.DECISION_CHANGED,
            actor=actor,
            from_status=old_status,
            to_status=GuestVisitStatus.PENDING,
            comment=comment or "Заявка возвращена в работу.",
        )
        notify_guest_visit(
            visit,
            "guest_visit_returned_to_work",
            get_guest_admin_users(),
            actor=actor,
            title="Гостевая заявка возвращена в работу",
            message=f"Заявка для {visit.guest.full_name} возвращена на рассмотрение.",
        )
        GuestLdapService().sync_guest_for_visit(visit)
        return visit

    @classmethod
    def revoke(cls, visit: GuestVisit, *, actor, comment: str = "") -> GuestVisit:
        if visit.status != GuestVisitStatus.APPROVED:
            raise ValueError("Отозвать можно только одобренный гостевой доступ.")
        visit.revoked_by = actor
        visit.revoked_at = timezone.now()
        visit.revoke_reason = comment
        cls._set_status(
            visit,
            GuestVisitStatus.REVOKED,
            actor=actor,
            event_type=GuestVisitEventType.REVOKED,
            comment=comment,
            update_fields=["revoked_by", "revoked_at", "revoke_reason"],
        )
        notify_guest_visit(
            visit,
            "guest_visit_revoked",
            [visit.inviter],
            actor=actor,
            title="Гостевой доступ отозван",
            message=f"Доступ гостя {visit.guest.full_name} отозван.",
        )
        GuestLdapService().disable_guest_if_no_active_visits(visit.guest, visit=visit)
        return visit

    @classmethod
    def expire(cls, visit: GuestVisit) -> GuestVisit:
        if visit.status != GuestVisitStatus.APPROVED:
            raise ValueError("Истечь может только одобренный гостевой доступ.")
        visit.expired_at = timezone.now()
        cls._set_status(
            visit,
            GuestVisitStatus.EXPIRED,
            actor=None,
            event_type=GuestVisitEventType.EXPIRED,
            update_fields=["expired_at"],
        )
        if getattr(settings, "GUESTS_NOTIFY_ON_EXPIRATION", True):
            notify_guest_visit(
                visit,
                "guest_visit_expired",
                [visit.inviter],
                title="Гостевой доступ истек",
                message=f"Доступ гостя {visit.guest.full_name} истек.",
            )
        GuestLdapService().disable_guest_if_no_active_visits(visit.guest, visit=visit)
        return visit


class GuestLdapService:
    @staticmethod
    def _is_ldap_write_enabled() -> bool:
        return bool(
            getattr(settings, "LDAP_ENABLED", False)
            and getattr(settings, "LDAP_WRITE_ENABLED", False)
        )

    def _should_be_in_active_ou(self, guest: Guest) -> bool:
        if guest.is_blacklisted:
            return False
        return guest.visits.filter(
            status=GuestVisitStatus.APPROVED,
            inviter_inactive=False,
            inviter__is_active=True,
        ).filter(
            Q(unlimited=True)
            | (
                Q(access_starts_at__lte=timezone.now())
                & (
                    Q(access_expires_at__isnull=True)
                    | Q(access_expires_at__gt=timezone.now())
                )
            )
        ).exists()

    def _get_state_dn(self, guest: Guest) -> str:
        return (
            LdapSyncState.objects.filter(model="guest", object_pk=str(guest.pk))
            .values_list("ldap_dn", flat=True)
            .first()
            or ""
        )

    def _touch_state(self, guest: Guest, dn: str) -> None:
        state, _ = LdapSyncState.objects.get_or_create(
            model="guest",
            object_pk=str(guest.pk),
        )
        state.touch(ldap_dn=dn, sync_dir="django")

    def _record_skip(
        self,
        guest: Guest,
        visit: GuestVisit | None = None,
        *,
        in_active_ou: bool,
    ) -> None:
        guest.is_active = in_active_ou
        guest.ldap_last_error = ""
        guest.ldap_last_synced_at = timezone.now()
        guest.save(
            update_fields=[
                "is_active",
                "ldap_last_error",
                "ldap_last_synced_at",
                "updated_at",
            ]
        )
        if visit:
            record_guest_event(
                visit,
                GuestVisitEventType.LDAP_SKIPPED,
                metadata={"reason": "LDAP write is disabled"},
            )

    def sync_guest_for_visit(
        self,
        visit: GuestVisit,
        *,
        enqueue_on_error: bool = True,
        raise_on_error: bool = False,
    ) -> None:
        self.sync_guest(
            visit.guest,
            visit=visit,
            enqueue_on_error=enqueue_on_error,
            raise_on_error=raise_on_error,
        )

    def sync_guest(
        self,
        guest: Guest,
        visit: GuestVisit | None = None,
        *,
        enqueue_on_error: bool = True,
        raise_on_error: bool = False,
    ) -> None:
        in_active_ou = self._should_be_in_active_ou(guest)
        if not self._is_ldap_write_enabled():
            self._record_skip(guest, visit, in_active_ou=in_active_ou)
            return

        current_dn = self._get_state_dn(guest)
        try:
            existing_dn = LdapGuestUser.find_existing_dn_for_guest(guest) or current_dn
            if existing_dn:
                try:
                    result = LdapGuestUser.sync_existing_for_guest(
                        guest,
                        existing_dn,
                        in_active_ou,
                    )
                    event_type = (
                        GuestVisitEventType.LDAP_ENABLED
                        if in_active_ou
                        else GuestVisitEventType.LDAP_DISABLED
                    )
                except LdapGuestUser.DoesNotExist:
                    result = self._create_or_adopt_guest_account(guest, in_active_ou)
                    event_type = GuestVisitEventType.LDAP_CREATED
            else:
                result = self._create_or_adopt_guest_account(guest, in_active_ou)
                event_type = GuestVisitEventType.LDAP_CREATED

            self._touch_state(guest, result.dn)
            guest.is_active = in_active_ou
            guest.ldap_username = result.sam_account_name
            guest.ldap_upn = result.user_principal_name
            guest.ldap_last_error = ""
            guest.ldap_last_synced_at = timezone.now()
            guest.save(
                update_fields=[
                    "is_active",
                    "ldap_username",
                    "ldap_upn",
                    "ldap_last_error",
                    "ldap_last_synced_at",
                    "updated_at",
                ]
            )
            if visit:
                record_guest_event(
                    visit,
                    event_type,
                    metadata={
                        "ldap_dn": result.dn,
                        "in_active_ou": in_active_ou,
                        "userAccountControl": str(result.user_account_control),
                    },
                )
            self.complete_pending_guest_syncs(guest)
        except Exception as exc:
            guest.ldap_last_error = str(exc)[:2000]
            guest.save(update_fields=["ldap_last_error", "updated_at"])
            if visit:
                record_guest_event(
                    visit,
                    GuestVisitEventType.LDAP_FAILED,
                    comment=str(exc),
            )
            if enqueue_on_error:
                self.enqueue_guest_sync(guest, operation="guest_sync")
            notify_visit = visit or guest.visits.order_by("-created_at").first()
            if notify_visit:
                notify_guest_visit(
                    notify_visit,
                    "guest_ldap_failed",
                    get_guest_admin_users(),
                    title="Ошибка LDAP для гостя",
                    message=str(exc),
                )
            if raise_on_error:
                raise

    def _create_or_adopt_guest_account(
        self,
        guest: Guest,
        in_active_ou: bool,
    ):
        try:
            return LdapGuestUser.create_for_guest(guest, in_active_ou)
        except GuestEmployeeNumberConflict as exc:
            if not LdapGuestUser.is_guest_dn(exc.dn):
                raise
            return LdapGuestUser.sync_existing_for_guest(
                guest,
                exc.dn,
                in_active_ou,
            )

    def disable_guest(
        self,
        guest: Guest,
        visit: GuestVisit | None = None,
        *,
        enqueue_on_error: bool = True,
        raise_on_error: bool = False,
    ) -> None:
        self.sync_guest(
            guest,
            visit=visit,
            enqueue_on_error=enqueue_on_error,
            raise_on_error=raise_on_error,
        )

    def blacklist_guest(
        self,
        guest: Guest,
        *,
        enqueue_on_error: bool = True,
        raise_on_error: bool = False,
    ) -> None:
        guest.is_blacklisted = True
        guest.save(update_fields=["is_blacklisted", "updated_at"])
        self.disable_guest(
            guest,
            enqueue_on_error=enqueue_on_error,
            raise_on_error=raise_on_error,
        )

    def unblacklist_guest(
        self,
        guest: Guest,
        *,
        enqueue_on_error: bool = True,
        raise_on_error: bool = False,
    ) -> None:
        guest.is_blacklisted = False
        guest.save(update_fields=["is_blacklisted", "updated_at"])
        self.sync_guest(
            guest,
            enqueue_on_error=enqueue_on_error,
            raise_on_error=raise_on_error,
        )

    def disable_guest_if_no_active_visits(
        self,
        guest: Guest,
        visit: GuestVisit | None = None,
        *,
        enqueue_on_error: bool = True,
        raise_on_error: bool = False,
    ) -> None:
        if not self._should_be_in_active_ou(guest):
            self.disable_guest(
                guest,
                visit=visit,
                enqueue_on_error=enqueue_on_error,
                raise_on_error=raise_on_error,
            )

    @staticmethod
    def complete_pending_guest_syncs(guest: Guest) -> None:
        LdapSyncQueue.objects.filter(
            operation__in=["guest_sync", "guest_disable"],
            model_name="guest",
            object_pk=str(guest.pk),
            status=LdapSyncQueue.Status.PENDING,
        ).update(
            status=LdapSyncQueue.Status.COMPLETED,
            last_error="",
            next_retry_at=None,
            updated_at=timezone.now(),
        )

    @staticmethod
    def enqueue_guest_sync(guest: Guest, *, operation: str = "guest_sync") -> None:
        payload = {"guest_id": str(guest.pk), "_operation": operation}
        pending = LdapSyncQueue.objects.filter(
            operation=operation,
            model_name="guest",
            object_pk=str(guest.pk),
            status=LdapSyncQueue.Status.PENDING,
        ).order_by("created_at")
        item = pending.first()
        if item:
            pending.exclude(pk=item.pk).update(
                status=LdapSyncQueue.Status.COMPLETED,
                last_error="",
                next_retry_at=None,
                updated_at=timezone.now(),
            )
            item.payload = payload
            item.next_retry_at = None
            item.save(update_fields=["payload", "next_retry_at", "updated_at"])
            return

        LdapSyncQueue.objects.create(
            operation=operation,
            model_name="guest",
            object_pk=str(guest.pk),
            payload=payload,
        )
