import pytest

from datetime import timedelta
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone

from documents.models import Document
from filer.models import Folder
from guests.constants import GuestVisitStatus
from guests.models import Guest, GuestVisit


TINY_PNG_BASE64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJ"
    "AAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
)


def _results(payload):
    return payload["results"] if isinstance(payload, dict) and "results" in payload else payload


@pytest.mark.django_db
def test_user_can_create_and_submit_guest_visit(auth_client_factory, user_factory):
    user = user_factory()
    client = auth_client_factory(user)

    response = client.post(
        "/api/v1/guests/visits/",
        {
            "guest": {
                "first_name": "Maria",
                "last_name": "Guest",
                "organization": "Vendor",
            },
            "purpose": "Wi-Fi access",
            "date_from": "2035-06-15",
            "date_to": "2035-06-18",
            "all_day": True,
        },
        format="json",
    )

    assert response.status_code == 201
    assert response.json()["status"] == GuestVisitStatus.PENDING
    visit_id = response.json()["id"]
    visit = GuestVisit.objects.get(pk=visit_id)
    assert visit.inviter == user
    assert visit.submitted_at is not None
    assert timezone.localtime(visit.access_expires_at).date().isoformat() == "2035-06-19"

    submit = client.post(f"/api/v1/guests/visits/{visit_id}/submit/")
    assert submit.status_code == 200
    assert submit.json()["status"] == GuestVisitStatus.PENDING


@pytest.mark.django_db
def test_user_can_create_guest_visit_without_guest_last_name(
    auth_client_factory,
    user_factory,
):
    user = user_factory()
    client = auth_client_factory(user)

    response = client.post(
        "/api/v1/guests/visits/",
        {
            "guest": {
                "first_name": "SingleName",
            },
            "purpose": "Visitor access",
            "date_from": "2035-06-15",
            "date_to": "2035-06-15",
            "all_day": True,
        },
        format="json",
    )

    assert response.status_code == 201
    visit = GuestVisit.objects.get(pk=response.json()["id"])
    assert visit.guest.first_name == "SingleName"
    assert visit.guest.last_name == ""
    assert response.json()["guest"]["full_name"] == "SingleName"


@pytest.mark.django_db
def test_user_can_create_guest_visit_with_guest_avatar(
    settings,
    tmp_path,
    auth_client_factory,
    user_factory,
):
    settings.MEDIA_ROOT = tmp_path
    user = user_factory()
    client = auth_client_factory(user)

    response = client.post(
        "/api/v1/guests/visits/",
        {
            "guest": {
                "first_name": "Avatar",
                "last_name": "Guest",
                "avatar": f"data:image/png;base64,{TINY_PNG_BASE64}",
            },
            "purpose": "Photo for downstream services",
            "date_from": "2035-06-15",
            "date_to": "2035-06-15",
            "all_day": True,
        },
        format="json",
    )

    assert response.status_code == 201
    visit = GuestVisit.objects.get(pk=response.json()["id"])
    assert visit.guest.avatar
    assert response.json()["guest"]["avatar"].startswith("data:image/")


@pytest.mark.django_db
def test_cannot_create_overlapping_guest_visit_for_same_guest(
    auth_client_factory,
    user_factory,
):
    user = user_factory()
    client = auth_client_factory(user)
    guest = Guest.objects.create(first_name="Overlap", last_name="Guest")

    first = client.post(
        "/api/v1/guests/visits/",
        {
            "guest_id": guest.id,
            "purpose": "First access",
            "date_from": "2035-06-15",
            "date_to": "2035-06-18",
            "all_day": True,
        },
        format="json",
    )
    overlapping = client.post(
        "/api/v1/guests/visits/",
        {
            "guest_id": guest.id,
            "purpose": "Overlapping access",
            "date_from": "2035-06-18",
            "date_to": "2035-06-20",
            "all_day": True,
        },
        format="json",
    )

    assert first.status_code == 201
    assert overlapping.status_code == 400
    assert "пересекающимся периодом" in str(overlapping.json())


@pytest.mark.django_db
def test_adjacent_guest_visit_period_is_allowed(
    auth_client_factory,
    user_factory,
):
    user = user_factory()
    client = auth_client_factory(user)
    guest = Guest.objects.create(first_name="Adjacent", last_name="Guest")

    first = client.post(
        "/api/v1/guests/visits/",
        {
            "guest_id": guest.id,
            "purpose": "First access",
            "date_from": "2035-06-15",
            "date_to": "2035-06-18",
            "all_day": True,
        },
        format="json",
    )
    adjacent = client.post(
        "/api/v1/guests/visits/",
        {
            "guest_id": guest.id,
            "purpose": "Next access",
            "date_from": "2035-06-19",
            "date_to": "2035-06-20",
            "all_day": True,
        },
        format="json",
    )

    assert first.status_code == 201
    assert adjacent.status_code == 201


@pytest.mark.django_db
def test_closed_guest_visit_does_not_block_overlapping_new_visit(
    auth_client_factory,
    user_factory,
):
    user = user_factory()
    client = auth_client_factory(user)
    guest = Guest.objects.create(first_name="Closed", last_name="Guest")

    first = client.post(
        "/api/v1/guests/visits/",
        {
            "guest_id": guest.id,
            "purpose": "No longer needed",
            "date_from": "2035-06-15",
            "date_to": "2035-06-18",
            "all_day": True,
        },
        format="json",
    )
    cancel = client.post(f"/api/v1/guests/visits/{first.json()['id']}/cancel/")
    next_visit = client.post(
        "/api/v1/guests/visits/",
        {
            "guest_id": guest.id,
            "purpose": "Replacement access",
            "date_from": "2035-06-16",
            "date_to": "2035-06-17",
            "all_day": True,
        },
        format="json",
    )

    assert first.status_code == 201
    assert cancel.status_code == 200
    assert next_visit.status_code == 201


@pytest.mark.django_db
def test_cannot_create_guest_visit_with_expired_period(
    auth_client_factory,
    user_factory,
):
    user = user_factory()
    client = auth_client_factory(user)
    yesterday = timezone.localdate() - timedelta(days=1)

    response = client.post(
        "/api/v1/guests/visits/",
        {
            "guest": {"first_name": "Past", "last_name": "Guest"},
            "purpose": "Expired access",
            "date_from": yesterday.isoformat(),
            "date_to": yesterday.isoformat(),
            "all_day": True,
        },
        format="json",
    )

    assert response.status_code == 400
    assert "уже истек" in str(response.json())


@pytest.mark.django_db
def test_today_all_day_guest_visit_is_allowed(
    auth_client_factory,
    user_factory,
):
    user = user_factory()
    client = auth_client_factory(user)
    today = timezone.localdate()

    response = client.post(
        "/api/v1/guests/visits/",
        {
            "guest": {"first_name": "Today", "last_name": "Guest"},
            "purpose": "Today access",
            "date_from": today.isoformat(),
            "date_to": today.isoformat(),
            "all_day": True,
        },
        format="json",
    )

    assert response.status_code == 201


@pytest.mark.django_db
def test_existing_unlimited_guest_visit_blocks_new_visit_for_same_guest(
    auth_client_factory,
    user_factory,
):
    user = user_factory()
    client = auth_client_factory(user)
    guest = Guest.objects.create(first_name="Unlimited", last_name="Guest")

    unlimited = client.post(
        "/api/v1/guests/visits/",
        {
            "guest_id": guest.id,
            "purpose": "Permanent access",
            "unlimited": True,
        },
        format="json",
    )
    next_visit = client.post(
        "/api/v1/guests/visits/",
        {
            "guest_id": guest.id,
            "purpose": "Extra access",
            "date_from": "2035-06-15",
            "date_to": "2035-06-15",
            "all_day": True,
        },
        format="json",
    )

    assert unlimited.status_code == 201
    assert next_visit.status_code == 400
    assert "пересекающимся периодом" in str(next_visit.json())


@pytest.mark.django_db
def test_cannot_update_guest_visit_to_overlapping_period(
    auth_client_factory,
    user_factory,
):
    user = user_factory()
    admin = user_factory(staff=True)
    client = auth_client_factory(user)
    admin_client = auth_client_factory(admin)
    guest = Guest.objects.create(first_name="UpdateOverlap", last_name="Guest")
    first = client.post(
        "/api/v1/guests/visits/",
        {
            "guest_id": guest.id,
            "purpose": "First access",
            "date_from": "2035-06-15",
            "date_to": "2035-06-16",
            "all_day": True,
        },
        format="json",
    )
    second = client.post(
        "/api/v1/guests/visits/",
        {
            "guest_id": guest.id,
            "purpose": "Second access",
            "date_from": "2035-06-17",
            "date_to": "2035-06-18",
            "all_day": True,
        },
        format="json",
    )

    response = admin_client.patch(
        f"/api/v1/guests/visits/{second.json()['id']}/",
        {
            "date_from": "2035-06-16",
            "date_to": "2035-06-18",
            "all_day": True,
        },
        format="json",
    )

    assert first.status_code == 201
    assert second.status_code == 201
    assert response.status_code == 400
    assert "пересекающимся периодом" in str(response.json())


@pytest.mark.django_db
def test_admin_can_approve_guest_visit(auth_client_factory, user_factory):
    user = user_factory()
    admin = user_factory(staff=True)
    user_client = auth_client_factory(user)
    admin_client = auth_client_factory(admin)

    created = user_client.post(
        "/api/v1/guests/visits/",
        {
            "guest": {"first_name": "Alex", "last_name": "Guest"},
            "purpose": "Directory access",
            "date_from": "2035-06-15",
            "date_to": "2035-06-15",
        },
        format="json",
    )
    visit_id = created.json()["id"]
    user_client.post(f"/api/v1/guests/visits/{visit_id}/submit/")

    response = admin_client.post(
        f"/api/v1/guests/visits/{visit_id}/approve/",
        {"comment": "ok"},
        format="json",
    )

    assert response.status_code == 200
    assert response.json()["status"] == GuestVisitStatus.APPROVED


@pytest.mark.django_db
def test_admin_can_reject_approved_guest_visit(auth_client_factory, user_factory):
    user = user_factory()
    admin = user_factory(staff=True)
    user_client = auth_client_factory(user)
    admin_client = auth_client_factory(admin)

    created = user_client.post(
        "/api/v1/guests/visits/",
        {
            "guest": {"first_name": "Reject", "last_name": "Approved"},
            "purpose": "Access",
            "date_from": "2035-06-15",
            "date_to": "2035-06-15",
        },
        format="json",
    )
    visit_id = created.json()["id"]
    user_client.post(f"/api/v1/guests/visits/{visit_id}/submit/")
    admin_client.post(f"/api/v1/guests/visits/{visit_id}/approve/")

    response = admin_client.post(
        f"/api/v1/guests/visits/{visit_id}/reject/",
        {"comment": "Stop access"},
        format="json",
    )

    assert response.status_code == 200
    assert response.json()["status"] == GuestVisitStatus.REJECTED
    assert GuestVisit.objects.get(pk=visit_id).events.filter(
        event_type="decision_changed"
    ).exists()


@pytest.mark.django_db
def test_admin_can_request_info_author_can_provide_info(
    auth_client_factory,
    user_factory,
):
    user = user_factory()
    admin = user_factory(staff=True)
    user_client = auth_client_factory(user)
    admin_client = auth_client_factory(admin)

    created = user_client.post(
        "/api/v1/guests/visits/",
        {
            "guest": {"first_name": "Need", "last_name": "Info"},
            "purpose": "Access",
            "date_from": "2035-06-15",
            "date_to": "2035-06-15",
        },
        format="json",
    )
    visit_id = created.json()["id"]
    user_client.post(f"/api/v1/guests/visits/{visit_id}/submit/")

    request_info = admin_client.post(
        f"/api/v1/guests/visits/{visit_id}/request-info/",
        {"comment": "Add sponsor details"},
        format="json",
    )
    assert request_info.status_code == 200
    assert request_info.json()["status"] == GuestVisitStatus.NEEDS_INFO
    assert "admin_comment" not in request_info.json()

    comments_after_request = user_client.get(
        f"/api/v1/guests/visits/{visit_id}/comments/"
    )
    assert comments_after_request.status_code == 200
    assert comments_after_request.json()[0]["text"] == "Add sponsor details"
    assert (
        comments_after_request.json()[0]["metadata"]["guest_visit_comment_type"]
        == "info_request"
    )

    provide_info = user_client.post(
        f"/api/v1/guests/visits/{visit_id}/provide-info/",
        {"comment": "Sponsor added"},
        format="json",
    )
    assert provide_info.status_code == 200
    assert provide_info.json()["status"] == GuestVisitStatus.PENDING
    admin_detail_before_read = admin_client.get(
        f"/api/v1/guests/visits/{visit_id}/"
    )
    assert admin_detail_before_read.status_code == 200
    assert admin_detail_before_read.json()["has_unread_info_response"] is True
    visit = GuestVisit.objects.get(pk=visit_id)
    assert visit.events.filter(event_type="needs_info_requested").exists()
    assert visit.events.filter(event_type="info_provided").exists()
    comments_after_response = admin_client.get(
        f"/api/v1/guests/visits/{visit_id}/comments/"
    )
    assert [comment["text"] for comment in comments_after_response.json()] == [
        "Add sponsor details",
        "Sponsor added",
    ]
    assert (
        comments_after_response.json()[1]["metadata"]["guest_visit_comment_type"]
        == "info_response"
    )
    admin_detail_after_read = admin_client.get(
        f"/api/v1/guests/visits/{visit_id}/"
    )
    assert admin_detail_after_read.status_code == 200
    assert admin_detail_after_read.json()["has_unread_info_response"] is False


@pytest.mark.django_db
def test_author_cannot_provide_info_without_active_request(
    auth_client_factory,
    user_factory,
):
    user = user_factory()
    client = auth_client_factory(user)
    created = client.post(
        "/api/v1/guests/visits/",
        {
            "guest": {"first_name": "No", "last_name": "Question"},
            "purpose": "Access",
            "date_from": "2035-06-15",
            "date_to": "2035-06-15",
        },
        format="json",
    )

    response = client.post(
        f"/api/v1/guests/visits/{created.json()['id']}/provide-info/",
        {"comment": "answer without question"},
        format="json",
    )

    assert response.status_code == 400


@pytest.mark.django_db
def test_admin_can_revoke_guest_visit(auth_client_factory, user_factory):
    user = user_factory()
    admin = user_factory(staff=True)
    user_client = auth_client_factory(user)
    admin_client = auth_client_factory(admin)

    created = user_client.post(
        "/api/v1/guests/visits/",
        {
            "guest": {"first_name": "Revoke", "last_name": "Guest"},
            "purpose": "Access",
            "date_from": "2035-06-15",
            "date_to": "2035-06-15",
        },
        format="json",
    )
    visit_id = created.json()["id"]
    user_client.post(f"/api/v1/guests/visits/{visit_id}/submit/")
    admin_client.post(f"/api/v1/guests/visits/{visit_id}/approve/")

    response = admin_client.post(
        f"/api/v1/guests/visits/{visit_id}/revoke/",
        {"comment": "No longer needed"},
        format="json",
    )

    assert response.status_code == 200
    assert response.json()["status"] == GuestVisitStatus.REVOKED
    assert GuestVisit.objects.get(pk=visit_id).events.filter(event_type="revoked").exists()


@pytest.mark.django_db
def test_author_can_cancel_guest_visit(auth_client_factory, user_factory):
    user = user_factory()
    client = auth_client_factory(user)
    created = client.post(
        "/api/v1/guests/visits/",
        {
            "guest": {"first_name": "Cancel", "last_name": "Guest"},
            "purpose": "Access",
            "date_from": "2035-06-15",
            "date_to": "2035-06-15",
        },
        format="json",
    )
    visit_id = created.json()["id"]

    response = client.post(
        f"/api/v1/guests/visits/{visit_id}/cancel/",
        {"comment": "not needed"},
        format="json",
    )

    assert response.status_code == 200
    assert response.json()["status"] == GuestVisitStatus.CANCELLED
    assert response.json()["can_cancel"] is False
    assert response.json()["can_return_to_work"] is True


@pytest.mark.django_db
def test_author_can_return_cancelled_visit_to_work(auth_client_factory, user_factory):
    user = user_factory()
    client = auth_client_factory(user)
    created = client.post(
        "/api/v1/guests/visits/",
        {
            "guest": {"first_name": "Return", "last_name": "Guest"},
            "purpose": "Access",
            "date_from": "2035-06-15",
            "date_to": "2035-06-15",
        },
        format="json",
    )
    visit_id = created.json()["id"]
    client.post(
        f"/api/v1/guests/visits/{visit_id}/cancel/",
        {"comment": "pause"},
        format="json",
    )

    response = client.post(
        f"/api/v1/guests/visits/{visit_id}/return-to-work/",
        {"comment": "needed again"},
        format="json",
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == GuestVisitStatus.PENDING
    assert payload["cancelled_at"] is None
    assert payload["cancel_reason"] == ""
    visit = GuestVisit.objects.get(pk=visit_id)
    assert visit.events.filter(
        event_type="decision_changed",
        from_status=GuestVisitStatus.CANCELLED,
        to_status=GuestVisitStatus.PENDING,
    ).exists()


@pytest.mark.django_db
def test_author_can_delete_visit_and_recalculate_guest_access(
    settings,
    auth_client_factory,
    user_factory,
):
    settings.LDAP_ENABLED = False
    settings.LDAP_WRITE_ENABLED = False
    user = user_factory()
    client = auth_client_factory(user)
    guest = Guest.objects.create(first_name="Delete", last_name="Access", is_active=True)
    visit = GuestVisit.objects.create(
        guest=guest,
        inviter=user,
        purpose="Temporary access",
        status=GuestVisitStatus.APPROVED,
        access_starts_at=timezone.now() - timedelta(hours=1),
        access_expires_at=timezone.now() + timedelta(hours=1),
    )

    response = client.delete(f"/api/v1/guests/visits/{visit.id}/")

    assert response.status_code == 204
    assert not GuestVisit.objects.filter(pk=visit.id).exists()
    guest.refresh_from_db()
    assert guest.is_active is False
    assert guest.ldap_last_error == ""
    assert guest.ldap_last_synced_at is not None


@pytest.mark.django_db
def test_deleting_one_visit_keeps_guest_access_when_another_active_visit_exists(
    settings,
    auth_client_factory,
    user_factory,
):
    settings.LDAP_ENABLED = False
    settings.LDAP_WRITE_ENABLED = False
    user = user_factory()
    client = auth_client_factory(user)
    guest = Guest.objects.create(first_name="Keep", last_name="Access", is_active=True)
    first = GuestVisit.objects.create(
        guest=guest,
        inviter=user,
        purpose="First access",
        status=GuestVisitStatus.APPROVED,
        access_starts_at=timezone.now() - timedelta(hours=1),
        access_expires_at=timezone.now() + timedelta(hours=1),
    )
    second = GuestVisit.objects.create(
        guest=guest,
        inviter=user,
        purpose="Second access",
        status=GuestVisitStatus.APPROVED,
        access_starts_at=timezone.now() - timedelta(hours=1),
        access_expires_at=timezone.now() + timedelta(hours=1),
    )

    response = client.delete(f"/api/v1/guests/visits/{first.id}/")

    assert response.status_code == 204
    assert GuestVisit.objects.filter(pk=second.id).exists()
    guest.refresh_from_db()
    assert guest.is_active is True


@pytest.mark.django_db
def test_other_user_cannot_delete_guest_visit(auth_client_factory, user_factory):
    author = user_factory()
    other = user_factory()
    other_client = auth_client_factory(other)
    guest = Guest.objects.create(first_name="No", last_name="Delete")
    visit = GuestVisit.objects.create(
        guest=guest,
        inviter=author,
        purpose="Protected access",
        status=GuestVisitStatus.PENDING,
    )

    response = other_client.delete(f"/api/v1/guests/visits/{visit.id}/")

    assert response.status_code in {403, 404}
    assert GuestVisit.objects.filter(pk=visit.id).exists()


@pytest.mark.django_db
def test_guest_visit_action_flags_match_valid_transitions(
    auth_client_factory,
    user_factory,
):
    admin = user_factory(staff=True)
    inviter = user_factory()
    client = auth_client_factory(admin)
    guest = Guest.objects.create(first_name="Flags", last_name="Guest")

    def read_flags(status):
        visit = GuestVisit.objects.create(
            guest=guest,
            inviter=inviter,
            purpose=f"{status} flags",
            status=status,
            access_starts_at=timezone.now() - timedelta(days=1),
            access_expires_at=timezone.now() + timedelta(days=1),
        )
        response = client.get(f"/api/v1/guests/visits/{visit.id}/")
        assert response.status_code == 200
        payload = response.json()
        return {
            "approve": payload["can_approve"],
            "reject": payload["can_reject"],
            "request_info": payload["can_request_info"],
            "cancel": payload["can_cancel"],
            "revoke": payload["can_revoke"],
            "return_to_work": payload["can_return_to_work"],
            "delete": payload["can_delete"],
        }

    assert read_flags(GuestVisitStatus.DRAFT) == {
        "approve": False,
        "reject": False,
        "request_info": False,
        "cancel": True,
        "revoke": False,
        "return_to_work": False,
        "delete": True,
    }
    assert read_flags(GuestVisitStatus.PENDING) == {
        "approve": True,
        "reject": True,
        "request_info": True,
        "cancel": True,
        "revoke": False,
        "return_to_work": False,
        "delete": True,
    }
    assert read_flags(GuestVisitStatus.APPROVED) == {
        "approve": False,
        "reject": True,
        "request_info": False,
        "cancel": True,
        "revoke": True,
        "return_to_work": False,
        "delete": True,
    }
    assert read_flags(GuestVisitStatus.REJECTED) == {
        "approve": True,
        "reject": False,
        "request_info": False,
        "cancel": False,
        "revoke": False,
        "return_to_work": False,
        "delete": True,
    }
    assert read_flags(GuestVisitStatus.CANCELLED) == {
        "approve": False,
        "reject": False,
        "request_info": False,
        "cancel": False,
        "revoke": False,
        "return_to_work": True,
        "delete": True,
    }


@pytest.mark.django_db
def test_invalid_api_transitions_return_400(auth_client_factory, user_factory):
    user = user_factory()
    admin = user_factory(staff=True)
    admin_client = auth_client_factory(admin)
    guest = Guest.objects.create(first_name="Bad", last_name="Transition")
    visit = GuestVisit.objects.create(
        guest=guest,
        inviter=user,
        purpose="Access",
        status=GuestVisitStatus.DRAFT,
        access_starts_at=timezone.now() + timedelta(days=1),
        access_expires_at=timezone.now() + timedelta(days=2),
    )

    approve = admin_client.post(f"/api/v1/guests/visits/{visit.id}/approve/")
    request_info = admin_client.post(
        f"/api/v1/guests/visits/{visit.id}/request-info/",
        {"comment": "details"},
        format="json",
    )

    assert approve.status_code == 400
    assert request_info.status_code == 400


@pytest.mark.django_db
def test_non_admin_cannot_approve_guest_visit(auth_client_factory, user_factory):
    author = user_factory()
    other = user_factory()
    client = auth_client_factory(author)
    other_client = auth_client_factory(other)

    created = client.post(
        "/api/v1/guests/visits/",
        {
            "guest": {"first_name": "No", "last_name": "Approve"},
            "purpose": "Access",
            "date_from": "2035-06-15",
            "date_to": "2035-06-15",
        },
        format="json",
    )
    visit_id = created.json()["id"]
    client.post(f"/api/v1/guests/visits/{visit_id}/submit/")

    response = other_client.post(f"/api/v1/guests/visits/{visit_id}/approve/")

    assert response.status_code in {403, 404}


@pytest.mark.django_db
def test_view_all_permission_does_not_allow_decision(
    auth_client_factory,
    user_factory,
):
    author = user_factory()
    viewer = user_factory()
    decider = user_factory()
    ct = ContentType.objects.get_for_model(GuestVisit)
    viewer.user_permissions.add(
        Permission.objects.get(content_type=ct, codename="view_all_guestvisit")
    )
    decider.user_permissions.add(
        Permission.objects.get(content_type=ct, codename="decide_guestvisit")
    )
    author_client = auth_client_factory(author)
    viewer_client = auth_client_factory(viewer)
    decider_client = auth_client_factory(decider)

    created = author_client.post(
        "/api/v1/guests/visits/",
        {
            "guest": {"first_name": "Perm", "last_name": "Guest"},
            "purpose": "Access",
            "date_from": "2035-06-15",
            "date_to": "2035-06-15",
        },
        format="json",
    )
    visit_id = created.json()["id"]
    author_client.post(f"/api/v1/guests/visits/{visit_id}/submit/")

    assert viewer_client.get(f"/api/v1/guests/visits/{visit_id}/").status_code == 200
    denied = viewer_client.post(f"/api/v1/guests/visits/{visit_id}/approve/")
    assert denied.status_code == 403

    approved = decider_client.post(f"/api/v1/guests/visits/{visit_id}/approve/")
    assert approved.status_code == 200


@pytest.mark.django_db
def test_guest_visit_comments(auth_client_factory, user_factory):
    user = user_factory()
    client = auth_client_factory(user)
    created = client.post(
        "/api/v1/guests/visits/",
        {
            "guest": {"first_name": "Comment", "last_name": "Guest"},
            "purpose": "Access",
            "date_from": "2035-06-15",
            "date_to": "2035-06-15",
        },
        format="json",
    )
    visit_id = created.json()["id"]

    response = client.post(
        f"/api/v1/guests/visits/{visit_id}/comments/",
        {"text": "Need badge too"},
        format="json",
    )
    assert response.status_code == 201

    listed = client.get(f"/api/v1/guests/visits/{visit_id}/comments/")
    assert listed.status_code == 200
    assert listed.json()[0]["text"] == "Need badge too"


@pytest.mark.django_db
def test_guest_profile_comments_use_communications(
    auth_client_factory,
    user_factory,
):
    user = user_factory()
    client = auth_client_factory(user)

    created = client.post(
        "/api/v1/guests/visits/",
        {
            "guest": {"first_name": "Profile", "last_name": "Comment"},
            "guest_comment": "Bring printed pass",
            "purpose": "Access",
            "date_from": "2035-06-15",
            "date_to": "2035-06-15",
        },
        format="json",
    )

    assert created.status_code == 201
    assert "comment" not in created.json()["guest"]
    guest_id = created.json()["guest"]["id"]

    comments = client.get(f"/api/v1/guests/{guest_id}/comments/")
    assert comments.status_code == 200
    assert comments.json()[0]["text"] == "Bring printed pass"

    guests = _results(client.get("/api/v1/guests/").json())
    guest_payload = next(item for item in guests if item["id"] == guest_id)
    assert guest_payload["comments_count"] == 1
    assert guest_payload["visits_count"] == 1


@pytest.mark.django_db
def test_guest_profile_comment_delete_permissions(
    auth_client_factory,
    user_factory,
):
    author = user_factory()
    other = user_factory()
    author_client = auth_client_factory(author)
    other_client = auth_client_factory(other)
    guest = Guest.objects.create(
        first_name="Delete",
        last_name="GuestComment",
        created_by=author,
    )
    comment = author_client.post(
        f"/api/v1/guests/{guest.id}/comments/",
        {"text": "Temporary"},
        format="json",
    ).json()

    listed = other_client.get(f"/api/v1/guests/{guest.id}/comments/")
    denied = other_client.delete(
        f"/api/v1/guests/{guest.id}/comments/{comment['id']}/"
    )
    deleted = author_client.delete(
        f"/api/v1/guests/{guest.id}/comments/{comment['id']}/"
    )

    assert listed.status_code == 200
    assert listed.json()[0]["text"] == "Temporary"
    assert denied.status_code == 403
    assert deleted.status_code == 204
    assert author_client.get(f"/api/v1/guests/{guest.id}/comments/").json() == []


@pytest.mark.django_db
def test_guest_visit_comment_delete_permissions(auth_client_factory, user_factory):
    author = user_factory()
    other = user_factory()
    author_client = auth_client_factory(author)
    other_client = auth_client_factory(other)
    created = author_client.post(
        "/api/v1/guests/visits/",
        {
            "guest": {"first_name": "Delete", "last_name": "Comment"},
            "purpose": "Access",
            "date_from": "2035-06-15",
            "date_to": "2035-06-15",
        },
        format="json",
    )
    visit_id = created.json()["id"]
    comment = author_client.post(
        f"/api/v1/guests/visits/{visit_id}/comments/",
        {"text": "Temporary"},
        format="json",
    ).json()

    denied = other_client.delete(
        f"/api/v1/guests/visits/{visit_id}/comments/{comment['id']}/"
    )
    deleted = author_client.delete(
        f"/api/v1/guests/visits/{visit_id}/comments/{comment['id']}/"
    )

    assert denied.status_code in {403, 404}
    assert deleted.status_code == 204
    listed = author_client.get(f"/api/v1/guests/visits/{visit_id}/comments/")
    assert listed.json() == []


@pytest.mark.django_db
def test_guest_visit_documents_can_be_attached_and_removed(
    auth_client_factory,
    user_factory,
):
    user = user_factory()
    client = auth_client_factory(user)
    document = Document.objects.create(title="Guest passport", uploaded_by=user)
    created = client.post(
        "/api/v1/guests/visits/",
        {
            "guest": {"first_name": "Doc", "last_name": "Guest"},
            "purpose": "Access",
            "date_from": "2035-06-15",
            "date_to": "2035-06-15",
        },
        format="json",
    )
    visit_id = created.json()["id"]

    attach = client.post(
        f"/api/v1/guests/visits/{visit_id}/documents/",
        {"document_id": document.id},
        format="json",
    )
    assert attach.status_code == 200
    assert attach.json()["documents"][0]["id"] == document.id

    remove = client.delete(
        f"/api/v1/guests/visits/{visit_id}/documents/{document.id}/"
    )
    assert remove.status_code == 200
    assert remove.json()["documents"] == []
    visit = GuestVisit.objects.get(pk=visit_id)
    assert visit.events.filter(event_type="document_attached").exists()
    assert visit.events.filter(event_type="document_removed").exists()


@pytest.mark.django_db
def test_guest_visit_create_and_update_document_ids(auth_client_factory, user_factory):
    user = user_factory()
    admin = user_factory(staff=True)
    client = auth_client_factory(user)
    admin_client = auth_client_factory(admin)
    first = Document.objects.create(title="First document", uploaded_by=user)
    second = Document.objects.create(title="Second document", uploaded_by=user)

    created = client.post(
        "/api/v1/guests/visits/",
        {
            "guest": {"first_name": "DocIds", "last_name": "Guest"},
            "purpose": "Access",
            "date_from": "2035-06-15",
            "date_to": "2035-06-15",
            "document_ids": [first.id],
        },
        format="json",
    )
    visit_id = created.json()["id"]
    assert [doc["id"] for doc in created.json()["documents"]] == [first.id]
    admin_client.post(
        f"/api/v1/guests/visits/{visit_id}/request-info/",
        {"comment": "replace document"},
        format="json",
    )

    updated = client.patch(
        f"/api/v1/guests/visits/{visit_id}/",
        {"document_ids": [second.id], "purpose": "Updated"},
        format="json",
    )

    assert updated.status_code == 200
    assert [doc["id"] for doc in updated.json()["documents"]] == [second.id]
    assert updated.json()["purpose"] == "Updated"


@pytest.mark.django_db
def test_regular_user_can_reuse_existing_guest_from_registry(
    auth_client_factory,
    user_factory,
):
    owner = user_factory()
    other = user_factory()
    owner_client = auth_client_factory(owner)
    other_client = auth_client_factory(other)
    guest = Guest.objects.create(
        first_name="Reusable",
        last_name="Guest",
        organization="Known vendor",
    )
    GuestVisit.objects.create(
        guest=guest,
        inviter=owner,
        purpose="Previous visit",
        status=GuestVisitStatus.DRAFT,
    )

    allowed = owner_client.post(
        "/api/v1/guests/visits/",
        {
            "guest_id": guest.id,
            "purpose": "Reuse own guest",
            "date_from": "2035-06-15",
            "date_to": "2035-06-15",
        },
        format="json",
    )
    other_allowed = other_client.post(
        "/api/v1/guests/visits/",
        {
            "guest_id": guest.id,
            "purpose": "Reuse registry guest",
            "date_from": "2035-06-16",
            "date_to": "2035-06-16",
        },
        format="json",
    )

    assert allowed.status_code == 201
    assert other_allowed.status_code == 201


@pytest.mark.django_db
def test_author_can_attach_documents_while_visit_is_pending(
    auth_client_factory,
    user_factory,
):
    author = user_factory()
    admin = user_factory(staff=True)
    author_client = auth_client_factory(author)
    admin_client = auth_client_factory(admin)
    document = Document.objects.create(title="Editable status doc", uploaded_by=author)
    guest = Guest.objects.create(first_name="Document", last_name="Guard")
    visit = GuestVisit.objects.create(
        guest=guest,
        inviter=author,
        purpose="Pending visit",
        status=GuestVisitStatus.PENDING,
        access_starts_at=timezone.now(),
        access_expires_at=timezone.now() + timedelta(days=1),
    )

    allowed = author_client.post(
        f"/api/v1/guests/visits/{visit.id}/documents/",
        {"document_id": document.id},
        format="json",
    )
    visit.status = GuestVisitStatus.REJECTED
    visit.save(update_fields=["status", "updated_at"])
    denied = author_client.post(
        f"/api/v1/guests/visits/{visit.id}/documents/",
        {"document_id": document.id},
        format="json",
    )
    admin_allowed = admin_client.post(
        f"/api/v1/guests/visits/{visit.id}/documents/",
        {"document_id": document.id},
        format="json",
    )

    assert allowed.status_code == 200
    assert denied.status_code == 403
    assert admin_allowed.status_code == 200


@pytest.mark.django_db
def test_required_document_setting_blocks_submit_without_document(
    settings,
    auth_client_factory,
    user_factory,
):
    settings.GUESTS_REQUIRE_ID_DOCUMENT = True
    user = user_factory()
    client = auth_client_factory(user)
    response = client.post(
        "/api/v1/guests/visits/",
        {
            "guest": {"first_name": "Required", "last_name": "Document"},
            "purpose": "Access",
            "date_from": "2035-06-15",
            "date_to": "2035-06-15",
        },
        format="json",
    )

    assert response.status_code == 400
    assert "document_ids" in response.json()


@pytest.mark.django_db
def test_author_can_update_only_needs_info(auth_client_factory, user_factory):
    user = user_factory()
    admin = user_factory(staff=True)
    client = auth_client_factory(user)
    admin_client = auth_client_factory(admin)
    created = client.post(
        "/api/v1/guests/visits/",
        {
            "guest": {"first_name": "Update", "last_name": "Guest"},
            "purpose": "Original",
            "date_from": "2035-06-15",
            "date_to": "2035-06-15",
        },
        format="json",
    )
    visit_id = created.json()["id"]

    pending_update = client.patch(
        f"/api/v1/guests/visits/{visit_id}/",
        {"purpose": "Pending update"},
        format="json",
    )
    admin_client.post(
        f"/api/v1/guests/visits/{visit_id}/request-info/",
        {"comment": "fix"},
        format="json",
    )
    needs_info_update = client.patch(
        f"/api/v1/guests/visits/{visit_id}/",
        {"purpose": "Needs info update"},
        format="json",
    )

    assert created.json()["status"] == GuestVisitStatus.PENDING
    assert pending_update.status_code == 403
    assert needs_info_update.status_code == 200


@pytest.mark.django_db
def test_guest_visit_list_scopes_filters_and_search(auth_client_factory, user_factory):
    admin = user_factory(staff=True)
    author = user_factory()
    other = user_factory()
    admin_client = auth_client_factory(admin)
    author_client = auth_client_factory(author)
    vendor_guest = Guest.objects.create(
        first_name="Vendor",
        last_name="Alpha",
        organization="Acme",
        email="vendor@example.test",
    )
    other_guest = Guest.objects.create(
        first_name="Other",
        last_name="Beta",
        organization="OtherOrg",
    )
    pending = GuestVisit.objects.create(
        guest=vendor_guest,
        inviter=author,
        purpose="Network access",
        status=GuestVisitStatus.PENDING,
        access_starts_at=timezone.now(),
        access_expires_at=timezone.now() + timedelta(days=1),
        unlimited=False,
    )
    GuestVisit.objects.create(
        guest=other_guest,
        inviter=other,
        purpose="Other access",
        status=GuestVisitStatus.APPROVED,
        access_starts_at=timezone.now(),
        access_expires_at=timezone.now() + timedelta(days=1),
        unlimited=True,
    )

    own = author_client.get("/api/v1/guests/visits/?scope=all")
    pending_admin = admin_client.get("/api/v1/guests/visits/?scope=pending_decision")
    search_admin = admin_client.get("/api/v1/guests/visits/?q=Acme")
    filtered_admin = admin_client.get(
        f"/api/v1/guests/visits/?guest_id={vendor_guest.id}&"
        f"inviter_id={author.id}&status=pending&unlimited=false"
    )

    assert [item["id"] for item in _results(own.json())] == [pending.id]
    assert [item["id"] for item in _results(pending_admin.json())] == [pending.id]
    assert [item["id"] for item in _results(search_admin.json())] == [pending.id]
    assert [item["id"] for item in _results(filtered_admin.json())] == [pending.id]


@pytest.mark.django_db
def test_guest_admin_endpoints_permissions_and_actions(
    auth_client_factory,
    user_factory,
):
    admin = user_factory(staff=True)
    regular = user_factory()
    admin_client = auth_client_factory(admin)
    regular_client = auth_client_factory(regular)
    guest = Guest.objects.create(
        first_name="Admin",
        last_name="Guest",
        organization="Acme",
    )

    listed = regular_client.get("/api/v1/guests/")
    retrieved = regular_client.get(f"/api/v1/guests/{guest.id}/")
    searched = regular_client.get("/api/v1/guests/search/?q=Admin")
    denied_update = regular_client.patch(
        f"/api/v1/guests/{guest.id}/",
        {"comment": "regular edit"},
        format="json",
    )
    denied_blacklist = regular_client.post(f"/api/v1/guests/{guest.id}/blacklist/")
    admin_listed = admin_client.get("/api/v1/guests/?q=Acme")
    updated = admin_client.patch(
        f"/api/v1/guests/{guest.id}/",
        {"comment": "checked", "organization": "Updated Org"},
        format="json",
    )
    blacklisted = admin_client.post(f"/api/v1/guests/{guest.id}/blacklist/")
    restored = admin_client.post(f"/api/v1/guests/{guest.id}/unblacklist/")

    assert listed.status_code == 200
    assert [item["id"] for item in _results(listed.json())] == [guest.id]
    assert retrieved.status_code == 200
    assert retrieved.json()["id"] == guest.id
    assert searched.json()[0]["id"] == guest.id
    assert denied_update.status_code == 403
    assert denied_blacklist.status_code == 403
    assert [item["id"] for item in _results(admin_listed.json())] == [guest.id]
    assert updated.status_code == 200
    assert updated.json()["organization"] == "Updated Org"
    assert "ldap_enabled" not in _results(listed.json())[0]
    assert blacklisted.status_code == 200
    assert blacklisted.json()["is_blacklisted"] is True
    assert blacklisted.json()["is_active"] is False
    assert restored.status_code == 200
    assert restored.json()["is_blacklisted"] is False


@pytest.mark.django_db
def test_guest_update_triggers_ldap_sync(
    settings,
    tmp_path,
    monkeypatch,
    auth_client_factory,
    user_factory,
):
    settings.MEDIA_ROOT = tmp_path
    admin = user_factory(staff=True)
    client = auth_client_factory(admin)
    guest = Guest.objects.create(first_name="Photo", last_name="Guest")
    synced_guest_ids = []

    def fake_sync(self, guest, **kwargs):
        synced_guest_ids.append(guest.id)

    monkeypatch.setattr("api.v1.guests.views.GuestLdapService.sync_guest", fake_sync)

    response = client.patch(
        f"/api/v1/guests/{guest.id}/",
        {
            "avatar": f"data:image/png;base64,{TINY_PNG_BASE64}",
            "phone": "+70000000000",
        },
        format="json",
    )

    assert response.status_code == 200
    guest.refresh_from_db()
    assert guest.avatar
    assert response.json()["avatar"].startswith("data:image/")
    assert synced_guest_ids == [guest.id]


@pytest.mark.django_db
def test_guest_admin_list_filters_and_ordering(auth_client_factory, user_factory):
    admin = user_factory(staff=True)
    client = auth_client_factory(admin)
    Guest.objects.create(
        first_name="First",
        last_name="Alpha",
        organization="AlphaOrg",
        is_active=True,
        is_blacklisted=False,
    )
    second = Guest.objects.create(
        first_name="Second",
        last_name="Zeta",
        organization="ZetaOrg",
        is_active=False,
        is_blacklisted=True,
    )

    inactive = client.get("/api/v1/guests/?is_active=false")
    blacklisted = client.get("/api/v1/guests/?is_blacklisted=true")
    ordered = client.get("/api/v1/guests/?ordering=-last_name")

    assert [item["id"] for item in _results(inactive.json())] == [second.id]
    assert [item["id"] for item in _results(blacklisted.json())] == [second.id]
    assert _results(ordered.json())[0]["id"] == second.id


@pytest.mark.django_db
def test_guest_document_upload_creates_guest_folder_and_relation(
    auth_client_factory,
    user_factory,
):
    user = user_factory()
    client = auth_client_factory(user)
    guest = Guest.objects.create(first_name="Doc", last_name="Guest")
    upload = SimpleUploadedFile(
        "passport.txt",
        b"passport payload",
        content_type="text/plain",
    )

    response = client.post(
        f"/api/v1/guests/{guest.id}/documents/",
        {"file": upload, "title": "Passport"},
        format="multipart",
    )

    assert response.status_code == 201
    guest.refresh_from_db()
    document_id = response.json()["document"]["id"]
    document = Document.objects.get(pk=document_id)
    assert guest.document_folder is not None
    assert guest.document_folder.parent.name == "guests"
    assert guest.document_folder.name == "Guest Doc"
    assert document.folder_id == guest.document_folder_id
    assert document.sent_to_all is False
    assert guest.documents.filter(pk=document.id).exists()


@pytest.mark.django_db
def test_guest_document_folder_names_are_unique(auth_client_factory, user_factory):
    user = user_factory()
    client = auth_client_factory(user)
    first = Guest.objects.create(first_name="Same", last_name="Name")
    second = Guest.objects.create(first_name="Same", last_name="Name")

    for guest in (first, second):
        client.post(
            f"/api/v1/guests/{guest.id}/documents/",
            {
                "file": SimpleUploadedFile(
                    f"{guest.id}.txt",
                    b"payload",
                    content_type="text/plain",
                ),
            },
            format="multipart",
        )

    first.refresh_from_db()
    second.refresh_from_db()
    assert first.document_folder.name == "Name Same"
    assert second.document_folder.name == "Name Same (2)"


@pytest.mark.django_db
def test_guest_managed_folder_cannot_be_edited_or_deleted_directly(
    auth_client_factory,
    user_factory,
):
    user = user_factory()
    client = auth_client_factory(user)
    guest = Guest.objects.create(first_name="Protected", last_name="Guest")
    guest.ensure_document_folder(owner=user)
    root_id = guest.document_folder.parent_id

    renamed = client.patch(
        f"/api/v1/folders/{guest.document_folder_id}/",
        {"name": "Manual rename"},
        format="json",
    )
    deleted_root = client.delete(f"/api/v1/folders/{root_id}/")

    assert renamed.status_code == 400
    assert deleted_root.status_code == 400
    assert Folder.objects.filter(pk=guest.document_folder_id).exists()


@pytest.mark.django_db
def test_guest_visit_document_attach_also_links_document_to_guest(
    auth_client_factory,
    user_factory,
):
    user = user_factory()
    client = auth_client_factory(user)
    guest = Guest.objects.create(first_name="Attach", last_name="Guest")
    visit = GuestVisit.objects.create(
        guest=guest,
        inviter=user,
        purpose="Attach document",
        status=GuestVisitStatus.DRAFT,
    )
    document = Document.objects.create(title="Existing document", uploaded_by=user)

    response = client.post(
        f"/api/v1/guests/visits/{visit.id}/documents/",
        {"document_id": document.id},
        format="json",
    )

    assert response.status_code == 200
    assert guest.documents.filter(pk=document.id).exists()


@pytest.mark.django_db
def test_manage_guestaccount_permission_can_sync_guest_ldap(
    auth_client_factory,
    monkeypatch,
    user_factory,
):
    manager = user_factory()
    viewer = user_factory()
    ct = ContentType.objects.get_for_model(GuestVisit)
    manager.user_permissions.add(
        Permission.objects.get(content_type=ct, codename="manage_guestaccount")
    )
    viewer.user_permissions.add(
        Permission.objects.get(content_type=ct, codename="view_all_guestvisit")
    )
    guest = Guest.objects.create(first_name="Sync", last_name="Guest")
    visit = GuestVisit.objects.create(
        guest=guest,
        inviter=user_factory(),
        purpose="Sync LDAP",
        status=GuestVisitStatus.APPROVED,
        access_starts_at=timezone.now(),
        access_expires_at=timezone.now() + timedelta(days=1),
    )
    manager_client = auth_client_factory(manager)
    viewer_client = auth_client_factory(viewer)
    monkeypatch.setattr(
        "api.v1.guests.views.GuestLdapService.sync_guest_for_visit",
        lambda *args, **kwargs: None,
    )

    allowed = manager_client.post(f"/api/v1/guests/visits/{visit.id}/sync-ldap/")
    denied = viewer_client.post(f"/api/v1/guests/visits/{visit.id}/sync-ldap/")

    assert allowed.status_code == 200
    assert denied.status_code == 403


@pytest.mark.django_db
def test_guest_sync_ldap_action_returns_error_on_ldap_failure(
    auth_client_factory,
    monkeypatch,
    user_factory,
):
    admin = user_factory(staff=True)
    guest = Guest.objects.create(first_name="Sync", last_name="Failure")
    client = auth_client_factory(admin)

    def fail_sync(*args, **kwargs):
        raise RuntimeError("LDAP failed")

    monkeypatch.setattr(
        "api.v1.guests.views.GuestLdapService.sync_guest",
        fail_sync,
    )

    response = client.post(f"/api/v1/guests/{guest.id}/sync-ldap/")

    assert response.status_code == 400
    assert "LDAP failed" in str(response.json())
