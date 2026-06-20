import pytest

from datetime import timedelta
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone

from documents.models import Document
from guests.constants import GuestVisitStatus
from guests.models import Guest, GuestVisit


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
            "date_from": "2026-06-15",
            "date_to": "2026-06-18",
            "all_day": True,
        },
        format="json",
    )

    assert response.status_code == 201
    visit_id = response.json()["id"]
    visit = GuestVisit.objects.get(pk=visit_id)
    assert visit.inviter == user
    assert timezone.localtime(visit.access_expires_at).date().isoformat() == "2026-06-19"

    submit = client.post(f"/api/v1/guests/visits/{visit_id}/submit/")
    assert submit.status_code == 200
    assert submit.json()["status"] == GuestVisitStatus.PENDING


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
            "date_from": "2026-06-15",
            "date_to": "2026-06-15",
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
            "date_from": "2026-06-15",
            "date_to": "2026-06-15",
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
            "date_from": "2026-06-15",
            "date_to": "2026-06-15",
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

    provide_info = user_client.post(
        f"/api/v1/guests/visits/{visit_id}/provide-info/",
        {"comment": "Sponsor added"},
        format="json",
    )
    assert provide_info.status_code == 200
    assert provide_info.json()["status"] == GuestVisitStatus.PENDING
    visit = GuestVisit.objects.get(pk=visit_id)
    assert visit.events.filter(event_type="needs_info_requested").exists()
    assert visit.events.filter(event_type="info_provided").exists()


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
            "date_from": "2026-06-15",
            "date_to": "2026-06-15",
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
            "date_from": "2026-06-15",
            "date_to": "2026-06-15",
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


@pytest.mark.django_db
def test_invalid_api_transitions_return_400(auth_client_factory, user_factory):
    user = user_factory()
    admin = user_factory(staff=True)
    client = auth_client_factory(user)
    admin_client = auth_client_factory(admin)
    created = client.post(
        "/api/v1/guests/visits/",
        {
            "guest": {"first_name": "Bad", "last_name": "Transition"},
            "purpose": "Access",
            "date_from": "2026-06-15",
            "date_to": "2026-06-15",
        },
        format="json",
    )
    visit_id = created.json()["id"]

    approve = admin_client.post(f"/api/v1/guests/visits/{visit_id}/approve/")
    request_info = admin_client.post(
        f"/api/v1/guests/visits/{visit_id}/request-info/",
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
            "date_from": "2026-06-15",
            "date_to": "2026-06-15",
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
            "date_from": "2026-06-15",
            "date_to": "2026-06-15",
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
            "date_from": "2026-06-15",
            "date_to": "2026-06-15",
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
            "date_from": "2026-06-15",
            "date_to": "2026-06-15",
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
            "date_from": "2026-06-15",
            "date_to": "2026-06-15",
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
    client = auth_client_factory(user)
    first = Document.objects.create(title="First document", uploaded_by=user)
    second = Document.objects.create(title="Second document", uploaded_by=user)

    created = client.post(
        "/api/v1/guests/visits/",
        {
            "guest": {"first_name": "DocIds", "last_name": "Guest"},
            "purpose": "Access",
            "date_from": "2026-06-15",
            "date_to": "2026-06-15",
            "document_ids": [first.id],
        },
        format="json",
    )
    visit_id = created.json()["id"]
    assert [doc["id"] for doc in created.json()["documents"]] == [first.id]

    updated = client.patch(
        f"/api/v1/guests/visits/{visit_id}/",
        {"document_ids": [second.id], "purpose": "Updated"},
        format="json",
    )

    assert updated.status_code == 200
    assert [doc["id"] for doc in updated.json()["documents"]] == [second.id]
    assert updated.json()["purpose"] == "Updated"


@pytest.mark.django_db
def test_required_document_setting_blocks_submit_without_document(
    settings,
    auth_client_factory,
    user_factory,
):
    settings.GUESTS_REQUIRE_ID_DOCUMENT = True
    user = user_factory()
    client = auth_client_factory(user)
    created = client.post(
        "/api/v1/guests/visits/",
        {
            "guest": {"first_name": "Required", "last_name": "Document"},
            "purpose": "Access",
            "date_from": "2026-06-15",
            "date_to": "2026-06-15",
        },
        format="json",
    )

    response = client.post(f"/api/v1/guests/visits/{created.json()['id']}/submit/")

    assert response.status_code == 400


@pytest.mark.django_db
def test_author_can_update_only_draft_or_needs_info(auth_client_factory, user_factory):
    user = user_factory()
    admin = user_factory(staff=True)
    client = auth_client_factory(user)
    admin_client = auth_client_factory(admin)
    created = client.post(
        "/api/v1/guests/visits/",
        {
            "guest": {"first_name": "Update", "last_name": "Guest"},
            "purpose": "Original",
            "date_from": "2026-06-15",
            "date_to": "2026-06-15",
        },
        format="json",
    )
    visit_id = created.json()["id"]

    draft_update = client.patch(
        f"/api/v1/guests/visits/{visit_id}/",
        {"purpose": "Draft update"},
        format="json",
    )
    client.post(f"/api/v1/guests/visits/{visit_id}/submit/")
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

    assert draft_update.status_code == 200
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

    denied = regular_client.get("/api/v1/guests/")
    listed = admin_client.get("/api/v1/guests/?q=Acme")
    searched = admin_client.get("/api/v1/guests/search/?q=Admin")
    updated = admin_client.patch(
        f"/api/v1/guests/{guest.id}/",
        {"comment": "checked", "organization": "Updated Org"},
        format="json",
    )
    deactivated = admin_client.post(f"/api/v1/guests/{guest.id}/deactivate/")

    assert denied.status_code == 403
    assert [item["id"] for item in _results(listed.json())] == [guest.id]
    assert searched.json()[0]["id"] == guest.id
    assert updated.status_code == 200
    assert updated.json()["organization"] == "Updated Org"
    assert deactivated.status_code == 200
    assert deactivated.json()["is_active"] is False


@pytest.mark.django_db
def test_manage_guestaccount_permission_can_sync_guest_ldap(
    auth_client_factory,
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

    allowed = manager_client.post(f"/api/v1/guests/visits/{visit.id}/sync-ldap/")
    denied = viewer_client.post(f"/api/v1/guests/visits/{visit.id}/sync-ldap/")

    assert allowed.status_code == 200
    assert denied.status_code == 403
