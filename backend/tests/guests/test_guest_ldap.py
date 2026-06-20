from contextlib import contextmanager
from datetime import timedelta

import pytest
from django.utils import timezone

from employees.ldap.services.constants import UserAccountControl
from employees.models import LdapSyncQueue, LdapSyncState
from employees.tasks import process_ldap_queue_item
from guests.constants import GuestVisitStatus
from guests.models import Guest, GuestVisit
from guests.services import GuestLdapService, GuestVisitWorkflow
from guests.tasks import execute_guest_queue_operation


class FakeLdapConnection:
    def __init__(self):
        self.entries = []
        self.add_calls = []
        self.modify_calls = []
        self.result = {}

    def search(self, *args, **kwargs):
        self.entries = []
        return True

    def add(self, dn, object_classes, attrs):
        self.add_calls.append((dn, object_classes, attrs))
        return True

    def modify(self, dn, changes):
        self.modify_calls.append((dn, changes))
        return True

    def unbind(self):
        return None


class FakeLdapEntry:
    def __init__(self, dn):
        self.entry_dn = dn


class ConflictingEmployeeNumberConnection(FakeLdapConnection):
    def search(self, *args, **kwargs):
        self.entries = [FakeLdapEntry("CN=Employee,OU=Users,DC=example,DC=test")]
        return True


class FakeLdapGuestUser:
    def __init__(self, dn):
        self.dn = dn
        self.moves = []
        self.saved = False

    def move_to(self, new_base_dn):
        self.moves.append(new_base_dn)
        rdn = self.dn.split(",", 1)[0]
        self.dn = f"{rdn},{new_base_dn}"

    def apply_guest(self, guest):
        self.sam_account_name = f"g{guest.id}"
        self.user_principal_name = f"g{guest.id}@guest.local"
        self.given_name = guest.first_name or ""
        self.sn = guest.last_name or "."
        self.display_name = guest.full_name or f"Guest {guest.id}"
        self.mail = guest.email or ""
        self.telephone_number = guest.phone or ""
        self.employee_number = str(guest.id)
        self.description = f"Guest account for {guest.organization}".strip()
        self.user_account_control = UserAccountControl.DISABLED

    def save(self):
        self.saved = True


@pytest.mark.django_db
def test_guest_ldap_service_writes_guest_id_to_employee_number(
    settings,
    monkeypatch,
    user_factory,
):
    settings.LDAP_ENABLED = True
    settings.LDAP_WRITE_ENABLED = True
    settings.LDAP_GUESTS_ACTIVE_BASE = "OU=Active,OU=Guests,DC=example,DC=test"
    settings.LDAP_GUESTS_DEACTIVATED_BASE = (
        "OU=Deactivated,OU=Guests,DC=example,DC=test"
    )
    settings.LDAP_BASE_DN = "DC=example,DC=test"

    fake_conn = FakeLdapConnection()

    @contextmanager
    def fake_ldap():
        yield fake_conn

    monkeypatch.setattr("guests.ldap.orm_models._ldap", fake_ldap)
    monkeypatch.setattr(
        "guests.ldap.orm_models.ensure_container_exists",
        lambda *a, **k: None,
    )
    monkeypatch.setattr(
        "guests.ldap.orm_models.UserPasswordService.set_password",
        lambda *a, **k: None,
    )

    inviter = user_factory()
    guest = Guest.objects.create(first_name="Ldap", last_name="Guest")
    visit = GuestVisit.objects.create(
        guest=guest,
        inviter=inviter,
        purpose="LDAP test",
        status=GuestVisitStatus.APPROVED,
        access_starts_at=timezone.now() - timedelta(minutes=1),
        access_expires_at=timezone.now() + timedelta(days=1),
    )

    GuestLdapService().sync_guest_for_visit(visit)

    assert fake_conn.add_calls
    attrs = fake_conn.add_calls[0][2]
    assert attrs["employeeNumber"] == str(guest.id)
    assert attrs["userAccountControl"] == UserAccountControl.DISABLED
    assert not fake_conn.modify_calls
    guest.refresh_from_db()
    assert guest.ldap_enabled is True
    assert guest.ldap_username == f"g{guest.id}"


@pytest.mark.django_db
def test_guest_ldap_service_disables_and_moves_to_deactivated(
    settings,
    monkeypatch,
):
    settings.LDAP_ENABLED = True
    settings.LDAP_WRITE_ENABLED = True
    settings.LDAP_GUESTS_ACTIVE_BASE = "OU=Active,OU=Guests,DC=example,DC=test"
    settings.LDAP_GUESTS_DEACTIVATED_BASE = (
        "OU=Deactivated,OU=Guests,DC=example,DC=test"
    )
    settings.LDAP_BASE_DN = "DC=example,DC=test"

    fake_conn = FakeLdapConnection()

    @contextmanager
    def fake_ldap():
        yield fake_conn

    guest = Guest.objects.create(
        first_name="Disable",
        last_name="Guest",
        is_active=False,
        ldap_enabled=True,
        ldap_username="g900000000000001",
    )
    active_dn = (
        f"CN=g{guest.id},OU=Active,OU=Guests,DC=example,DC=test"
    )
    LdapSyncState.objects.create(
        model="guest",
        object_pk=str(guest.id),
        ldap_dn=active_dn,
    )
    fake_orm_guest = FakeLdapGuestUser(active_dn)

    monkeypatch.setattr("guests.ldap.orm_models._ldap", fake_ldap)
    monkeypatch.setattr(
        "guests.ldap.orm_models.ensure_container_exists",
        lambda *a, **k: None,
    )
    monkeypatch.setattr(
        "guests.ldap.orm_models.LdapGuestUser.objects.get",
        lambda **kwargs: fake_orm_guest,
    )

    GuestLdapService().disable_guest(guest)

    guest.refresh_from_db()
    state = LdapSyncState.objects.get(model="guest", object_pk=str(guest.id))
    assert state.ldap_dn == (
        f"CN=g{guest.id},OU=Deactivated,OU=Guests,DC=example,DC=test"
    )
    assert guest.ldap_enabled is False
    assert fake_orm_guest.moves == ["OU=Deactivated,OU=Guests,DC=example,DC=test"]
    assert fake_orm_guest.saved is True
    assert fake_orm_guest.employee_number == str(guest.id)
    assert fake_orm_guest.user_account_control == UserAccountControl.DISABLED


@pytest.mark.django_db
def test_guest_ldap_service_moves_existing_guest_to_active_ou_without_enabling(
    settings,
    monkeypatch,
    user_factory,
):
    settings.LDAP_ENABLED = True
    settings.LDAP_WRITE_ENABLED = True
    settings.LDAP_GUESTS_ACTIVE_BASE = "OU=Active,OU=Guests,DC=example,DC=test"
    settings.LDAP_GUESTS_DEACTIVATED_BASE = (
        "OU=Deactivated,OU=Guests,DC=example,DC=test"
    )
    settings.LDAP_BASE_DN = "DC=example,DC=test"

    fake_conn = FakeLdapConnection()

    @contextmanager
    def fake_ldap():
        yield fake_conn

    inviter = user_factory()
    guest = Guest.objects.create(first_name="Active", last_name="Guest")
    deactivated_dn = f"CN=g{guest.id},OU=Deactivated,OU=Guests,DC=example,DC=test"
    LdapSyncState.objects.create(
        model="guest",
        object_pk=str(guest.id),
        ldap_dn=deactivated_dn,
    )
    GuestVisit.objects.create(
        guest=guest,
        inviter=inviter,
        purpose="Active LDAP move",
        status=GuestVisitStatus.APPROVED,
        access_starts_at=timezone.now() - timedelta(minutes=1),
        access_expires_at=timezone.now() + timedelta(days=1),
    )
    fake_orm_guest = FakeLdapGuestUser(deactivated_dn)

    monkeypatch.setattr("guests.ldap.orm_models._ldap", fake_ldap)
    monkeypatch.setattr(
        "guests.ldap.orm_models.ensure_container_exists",
        lambda *a, **k: None,
    )
    monkeypatch.setattr(
        "guests.ldap.orm_models.LdapGuestUser.objects.get",
        lambda **kwargs: fake_orm_guest,
    )

    GuestLdapService().sync_guest(guest)

    guest.refresh_from_db()
    state = LdapSyncState.objects.get(model="guest", object_pk=str(guest.id))
    assert fake_orm_guest.moves == ["OU=Active,OU=Guests,DC=example,DC=test"]
    assert fake_orm_guest.saved is True
    assert fake_orm_guest.user_account_control == UserAccountControl.DISABLED
    assert fake_conn.modify_calls == []
    assert state.ldap_dn == f"CN=g{guest.id},OU=Active,OU=Guests,DC=example,DC=test"
    assert guest.ldap_enabled is True


@pytest.mark.django_db
def test_guest_ldap_service_keeps_active_ou_when_other_active_visit_exists(
    settings,
    monkeypatch,
    user_factory,
):
    settings.LDAP_ENABLED = True
    settings.LDAP_WRITE_ENABLED = True
    settings.LDAP_GUESTS_ACTIVE_BASE = "OU=Active,OU=Guests,DC=example,DC=test"
    settings.LDAP_GUESTS_DEACTIVATED_BASE = (
        "OU=Deactivated,OU=Guests,DC=example,DC=test"
    )
    settings.LDAP_BASE_DN = "DC=example,DC=test"

    fake_conn = FakeLdapConnection()

    @contextmanager
    def fake_ldap():
        yield fake_conn

    inviter = user_factory()
    guest = Guest.objects.create(
        first_name="Multi",
        last_name="Visit",
        ldap_enabled=True,
    )
    active_dn = f"CN=g{guest.id},OU=Active,OU=Guests,DC=example,DC=test"
    LdapSyncState.objects.create(
        model="guest",
        object_pk=str(guest.id),
        ldap_dn=active_dn,
    )
    ending_visit = GuestVisit.objects.create(
        guest=guest,
        inviter=inviter,
        purpose="Ending",
        status=GuestVisitStatus.APPROVED,
        access_starts_at=timezone.now() - timedelta(days=2),
        access_expires_at=timezone.now() + timedelta(days=1),
    )
    GuestVisit.objects.create(
        guest=guest,
        inviter=inviter,
        purpose="Still active",
        status=GuestVisitStatus.APPROVED,
        access_starts_at=timezone.now() - timedelta(days=1),
        access_expires_at=timezone.now() + timedelta(days=2),
    )
    fake_orm_guest = FakeLdapGuestUser(active_dn)

    monkeypatch.setattr("guests.ldap.orm_models._ldap", fake_ldap)
    monkeypatch.setattr(
        "guests.ldap.orm_models.ensure_container_exists",
        lambda *a, **k: None,
    )
    monkeypatch.setattr(
        "guests.ldap.orm_models.LdapGuestUser.objects.get",
        lambda **kwargs: fake_orm_guest,
    )

    GuestVisitWorkflow.revoke(ending_visit, actor=inviter)

    guest.refresh_from_db()
    assert fake_orm_guest.moves == []
    assert guest.ldap_enabled is True


@pytest.mark.django_db
def test_execute_guest_queue_operation_dispatches_sync(monkeypatch):
    guest = Guest.objects.create(first_name="Queue", last_name="Guest")
    called = {}

    def fake_sync(self, synced_guest, *, enqueue_on_error=True, raise_on_error=False):
        called["guest_id"] = synced_guest.id
        called["enqueue_on_error"] = enqueue_on_error
        called["raise_on_error"] = raise_on_error

    monkeypatch.setattr("guests.services.GuestLdapService.sync_guest", fake_sync)

    execute_guest_queue_operation("guest_sync", {"guest_id": str(guest.id)})

    assert called["guest_id"] == guest.id
    assert called["enqueue_on_error"] is False
    assert called["raise_on_error"] is True


@pytest.mark.django_db
def test_process_ldap_queue_item_completes_guest_sync(
    settings,
    monkeypatch,
):
    settings.LDAP_ENABLED = True
    guest = Guest.objects.create(first_name="Queue", last_name="Complete")
    item = LdapSyncQueue.objects.create(
        operation="guest_sync",
        model_name="guest",
        object_pk=str(guest.id),
        payload={"guest_id": str(guest.id), "_operation": "guest_sync"},
    )
    called = {}

    def fake_sync(self, synced_guest, *, enqueue_on_error=True, raise_on_error=False):
        called["guest_id"] = synced_guest.id
        called["raise_on_error"] = raise_on_error

    monkeypatch.setattr("guests.services.GuestLdapService.sync_guest", fake_sync)

    process_ldap_queue_item.run(item.id)

    item.refresh_from_db()
    assert item.status == LdapSyncQueue.Status.COMPLETED
    assert called == {"guest_id": guest.id, "raise_on_error": True}


@pytest.mark.django_db
def test_process_ldap_queue_item_schedules_retry_on_guest_sync_error(
    settings,
    monkeypatch,
):
    settings.LDAP_ENABLED = True
    guest = Guest.objects.create(first_name="Queue", last_name="Retry")
    item = LdapSyncQueue.objects.create(
        operation="guest_sync",
        model_name="guest",
        object_pk=str(guest.id),
        payload={"guest_id": str(guest.id), "_operation": "guest_sync"},
    )

    def failing_sync(self, synced_guest, *, enqueue_on_error=True, raise_on_error=False):
        raise RuntimeError("retry me")

    monkeypatch.setattr("guests.services.GuestLdapService.sync_guest", failing_sync)

    process_ldap_queue_item.run(item.id)

    item.refresh_from_db()
    assert item.status == LdapSyncQueue.Status.PENDING
    assert item.attempts == 1
    assert "retry me" in item.last_error
    assert item.next_retry_at is not None


@pytest.mark.django_db
def test_guest_ldap_employee_number_conflict_queues_retry(
    settings,
    monkeypatch,
    user_factory,
):
    settings.LDAP_ENABLED = True
    settings.LDAP_WRITE_ENABLED = True
    settings.LDAP_GUESTS_ACTIVE_BASE = "OU=Active,OU=Guests,DC=example,DC=test"
    settings.LDAP_GUESTS_DEACTIVATED_BASE = (
        "OU=Deactivated,OU=Guests,DC=example,DC=test"
    )
    settings.LDAP_BASE_DN = "DC=example,DC=test"
    conflict_conn = ConflictingEmployeeNumberConnection()

    @contextmanager
    def fake_ldap():
        yield conflict_conn

    monkeypatch.setattr("guests.ldap.orm_models._ldap", fake_ldap)
    monkeypatch.setattr(
        "guests.ldap.orm_models.ensure_container_exists",
        lambda *a, **k: None,
    )
    inviter = user_factory()
    admin = user_factory(staff=True)
    guest = Guest.objects.create(first_name="Conflict", last_name="Guest")
    visit = GuestVisit.objects.create(
        guest=guest,
        inviter=inviter,
        purpose="Conflict",
        status=GuestVisitStatus.PENDING,
        access_starts_at=timezone.now() - timedelta(minutes=1),
        access_expires_at=timezone.now() + timedelta(days=1),
    )

    GuestVisitWorkflow.approve(visit, actor=admin)

    guest.refresh_from_db()
    assert "employeeNumber" in guest.ldap_last_error
    assert LdapSyncQueue.objects.filter(
        operation="guest_sync",
        model_name="guest",
        object_pk=str(guest.id),
    ).exists()


@pytest.mark.django_db
def test_approve_keeps_status_and_queues_retry_on_ldap_error(
    settings,
    monkeypatch,
    user_factory,
):
    settings.LDAP_ENABLED = True
    settings.LDAP_WRITE_ENABLED = True
    settings.LDAP_GUESTS_ACTIVE_BASE = "OU=Active,OU=Guests,DC=example,DC=test"
    settings.LDAP_GUESTS_DEACTIVATED_BASE = (
        "OU=Deactivated,OU=Guests,DC=example,DC=test"
    )
    settings.LDAP_BASE_DN = "DC=example,DC=test"

    @contextmanager
    def failing_ldap():
        raise RuntimeError("LDAP unavailable")
        yield

    monkeypatch.setattr("guests.ldap.orm_models._ldap", failing_ldap)

    inviter = user_factory()
    admin = user_factory(staff=True)
    guest = Guest.objects.create(first_name="Retry", last_name="Guest")
    visit = GuestVisit.objects.create(
        guest=guest,
        inviter=inviter,
        purpose="Retry LDAP",
        status=GuestVisitStatus.PENDING,
        access_starts_at=timezone.now() - timedelta(minutes=1),
        access_expires_at=timezone.now() + timedelta(days=1),
    )

    GuestVisitWorkflow.approve(visit, actor=admin)

    visit.refresh_from_db()
    guest.refresh_from_db()
    assert visit.status == GuestVisitStatus.APPROVED
    assert "LDAP unavailable" in guest.ldap_last_error
    assert visit.events.filter(event_type="ldap_failed").exists()
    assert LdapSyncQueue.objects.filter(
        operation="guest_sync",
        model_name="guest",
        object_pk=str(guest.id),
    ).exists()
