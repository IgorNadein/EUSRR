from datetime import timedelta

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.utils import timezone

from guests.constants import GUEST_ID_MIN, GUEST_ID_START, GuestVisitStatus
from guests.models import Guest, GuestVisit
from guests.services import GuestVisitWorkflow
from guests.tasks import (
    activate_due_guest_visits,
    detect_inactive_inviters,
    expire_guest_visits,
)


@pytest.mark.django_db
def test_guest_id_generated_in_guest_range(user_factory):
    user = user_factory()

    guest = Guest.objects.create(
        first_name="Ivan",
        last_name="Guest",
        created_by=user,
    )

    assert guest.id == GUEST_ID_START
    assert len(str(guest.id)) == 15
    assert str(guest.id).startswith("9")


@pytest.mark.django_db
def test_employee_id_cannot_enter_guest_range(user_factory):
    with pytest.raises(IntegrityError):
        user_factory(id=GUEST_ID_MIN, email="blocked@example.test")


@pytest.mark.django_db
def test_guest_visit_workflow_records_events(user_factory):
    inviter = user_factory()
    admin = user_factory(staff=True)
    guest = Guest.objects.create(first_name="Ann", last_name="Guest")
    visit = GuestVisit.objects.create(
        guest=guest,
        inviter=inviter,
        purpose="External integration access",
        access_starts_at=timezone.now() - timedelta(minutes=5),
        access_expires_at=timezone.now() + timedelta(days=1),
    )

    GuestVisitWorkflow.submit(visit, actor=inviter)
    visit.refresh_from_db()
    assert visit.status == GuestVisitStatus.PENDING

    GuestVisitWorkflow.approve(visit, actor=admin, comment="ok")
    visit.refresh_from_db()
    assert visit.status == GuestVisitStatus.APPROVED
    assert visit.decided_by == admin

    event_types = set(visit.events.values_list("event_type", flat=True))
    assert {"submitted", "approved"}.issubset(event_types)


@pytest.mark.django_db
def test_rejected_visit_can_be_approved_later(user_factory):
    inviter = user_factory()
    admin = user_factory(staff=True)
    guest = Guest.objects.create(first_name="Ben", last_name="Guest")
    visit = GuestVisit.objects.create(
        guest=guest,
        inviter=inviter,
        purpose="Temporary access",
        status=GuestVisitStatus.PENDING,
        access_starts_at=timezone.now(),
        access_expires_at=timezone.now() + timedelta(days=1),
    )

    GuestVisitWorkflow.reject(visit, actor=admin, comment="missing info")
    visit.refresh_from_db()
    assert visit.status == GuestVisitStatus.REJECTED

    GuestVisitWorkflow.approve(visit, actor=admin, comment="updated")
    visit.refresh_from_db()
    assert visit.status == GuestVisitStatus.APPROVED
    assert visit.events.filter(event_type="decision_changed").exists()


@pytest.mark.django_db
def test_unlimited_guest_visit_can_be_submitted_without_dates(user_factory):
    inviter = user_factory()
    guest = Guest.objects.create(first_name="No", last_name="Limit")
    visit = GuestVisit.objects.create(
        guest=guest,
        inviter=inviter,
        purpose="Long-term vendor access",
        unlimited=True,
    )

    GuestVisitWorkflow.submit(visit, actor=inviter)

    visit.refresh_from_db()
    assert visit.status == GuestVisitStatus.PENDING
    assert visit.access_expires_at is None


@pytest.mark.django_db
def test_expire_guest_visit_records_event_and_disables_guest(settings, user_factory):
    settings.GUESTS_NOTIFY_ON_EXPIRATION = False
    inviter = user_factory()
    guest = Guest.objects.create(first_name="Old", last_name="Guest")
    visit = GuestVisit.objects.create(
        guest=guest,
        inviter=inviter,
        purpose="Expired access",
        status=GuestVisitStatus.APPROVED,
        access_starts_at=timezone.now() - timedelta(days=2),
        access_expires_at=timezone.now() - timedelta(minutes=1),
    )

    GuestVisitWorkflow.expire(visit)

    visit.refresh_from_db()
    guest.refresh_from_db()
    assert visit.status == GuestVisitStatus.EXPIRED
    assert guest.ldap_last_synced_at is not None
    assert visit.events.filter(event_type="expired").exists()
    assert visit.events.filter(event_type="ldap_skipped").exists()


@pytest.mark.django_db
def test_detect_inactive_inviters_flags_risk_without_auto_disable(user_factory):
    admin = user_factory(staff=True)
    inviter = user_factory(active=False)
    guest = Guest.objects.create(first_name="Risk", last_name="Guest")
    visit = GuestVisit.objects.create(
        guest=guest,
        inviter=inviter,
        purpose="Active guest with inactive inviter",
        status=GuestVisitStatus.APPROVED,
        access_starts_at=timezone.now() - timedelta(days=1),
        access_expires_at=timezone.now() + timedelta(days=1),
    )

    detect_inactive_inviters.run()

    visit.refresh_from_db()
    guest.refresh_from_db()
    assert admin.is_staff
    assert visit.inviter_inactive is True
    assert guest.ldap_enabled is False
    assert visit.events.filter(event_type="inviter_inactive_detected").exists()


@pytest.mark.django_db
def test_guest_id_outside_guest_range_is_rejected():
    guest = Guest(
        id=GUEST_ID_MIN,
        first_name="Bad",
        last_name="Range",
    )

    with pytest.raises(ValidationError):
        guest.full_clean()


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("action", "status"),
    [
        ("approve", GuestVisitStatus.DRAFT),
        ("request_info", GuestVisitStatus.DRAFT),
        ("revoke", GuestVisitStatus.PENDING),
        ("expire", GuestVisitStatus.PENDING),
    ],
)
def test_guest_visit_workflow_rejects_invalid_transitions(
    action,
    status,
    user_factory,
):
    inviter = user_factory()
    admin = user_factory(staff=True)
    guest = Guest.objects.create(first_name="Invalid", last_name="Transition")
    visit = GuestVisit.objects.create(
        guest=guest,
        inviter=inviter,
        purpose="Invalid transition",
        status=status,
        access_starts_at=timezone.now() - timedelta(minutes=1),
        access_expires_at=timezone.now() + timedelta(days=1),
    )

    with pytest.raises(ValueError):
        if action == "approve":
            GuestVisitWorkflow.approve(visit, actor=admin)
        elif action == "request_info":
            GuestVisitWorkflow.request_info(visit, actor=admin, comment="details")
        elif action == "revoke":
            GuestVisitWorkflow.revoke(visit, actor=admin)
        elif action == "expire":
            GuestVisitWorkflow.expire(visit)


@pytest.mark.django_db
def test_approved_visit_can_be_rejected_later(user_factory):
    inviter = user_factory()
    admin = user_factory(staff=True)
    guest = Guest.objects.create(first_name="Decision", last_name="Change")
    visit = GuestVisit.objects.create(
        guest=guest,
        inviter=inviter,
        purpose="Decision change",
        status=GuestVisitStatus.APPROVED,
        access_starts_at=timezone.now() - timedelta(minutes=1),
        access_expires_at=timezone.now() + timedelta(days=1),
    )

    GuestVisitWorkflow.reject(visit, actor=admin, comment="revise")

    visit.refresh_from_db()
    assert visit.status == GuestVisitStatus.REJECTED
    assert visit.events.filter(event_type="decision_changed").exists()


@pytest.mark.django_db
def test_cancelled_or_expired_visit_cannot_be_cancelled(user_factory):
    inviter = user_factory()
    guest = Guest.objects.create(first_name="Final", last_name="State")
    visit = GuestVisit.objects.create(
        guest=guest,
        inviter=inviter,
        purpose="Final state",
        status=GuestVisitStatus.EXPIRED,
        access_starts_at=timezone.now() - timedelta(days=2),
        access_expires_at=timezone.now() - timedelta(days=1),
    )

    with pytest.raises(ValueError):
        GuestVisitWorkflow.cancel(visit, actor=inviter)


@pytest.mark.django_db
def test_expire_guest_visits_task_expires_due_visits(settings, user_factory):
    settings.GUESTS_NOTIFY_ON_EXPIRATION = False
    inviter = user_factory()
    guest = Guest.objects.create(first_name="Task", last_name="Expire")
    visit = GuestVisit.objects.create(
        guest=guest,
        inviter=inviter,
        purpose="Task expiration",
        status=GuestVisitStatus.APPROVED,
        access_starts_at=timezone.now() - timedelta(days=2),
        access_expires_at=timezone.now() - timedelta(minutes=1),
    )

    expire_guest_visits.run()

    visit.refresh_from_db()
    assert visit.status == GuestVisitStatus.EXPIRED
    assert visit.events.filter(event_type="expired").exists()


@pytest.mark.django_db
def test_activate_due_guest_visits_task_syncs_due_visit(monkeypatch, user_factory):
    inviter = user_factory()
    guest = Guest.objects.create(first_name="Task", last_name="Activate")
    visit = GuestVisit.objects.create(
        guest=guest,
        inviter=inviter,
        purpose="Task activation",
        status=GuestVisitStatus.APPROVED,
        access_starts_at=timezone.now() - timedelta(minutes=1),
        access_expires_at=timezone.now() + timedelta(days=1),
    )
    synced = []

    def fake_sync(self, synced_visit):
        synced.append(synced_visit.pk)

    monkeypatch.setattr("guests.tasks.GuestLdapService.sync_guest_for_visit", fake_sync)

    activate_due_guest_visits.run()

    assert synced == [visit.pk]
