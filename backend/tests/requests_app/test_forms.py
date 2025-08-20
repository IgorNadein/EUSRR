
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

pytestmark = pytest.mark.django_db


def _file(name="f.pdf", content=b"x", content_type="application/pdf"):
    return SimpleUploadedFile(name=name, content=content, content_type=content_type)


# -------------------- RequestForm --------------------


def test_request_form_valid_minimal():
    from requests_app.forms import RequestForm
    from requests_app.models import Request

    form = RequestForm(data={"type": Request.TYPE_OTHER, "comment": "ok"})
    assert form.is_valid()


def test_request_form_date_reverse_error():
    from requests_app.forms import RequestForm

    form = RequestForm(
        data={"type": "other", "date_from": "2025-01-10", "date_to": "2025-01-01"}
    )
    assert not form.is_valid()
    assert "date_to" in form.errors


def test_request_form_attachment_magic_missing_requires_both_ext_and_ct(monkeypatch):
    """
    Когда python-magic недоступен (_sniff_mime -> None), нужен И корректный content_type,
    И корректное расширение.
    """
    from requests_app import forms as F

    # эмулируем отсутствие python-magic
    monkeypatch.setattr(F, "_sniff_mime", lambda f: None)

    # валидный случай: jpeg + .jpg
    form_ok = F.RequestForm(
        data={"type": "other"},
        files={
            "attachment": _file(
                name="pic.jpg", content=b"abc", content_type="image/jpeg"
            )
        },
    )
    assert form_ok.is_valid()

    # невалидный: image/jpeg, но расширение .exe
    form_bad = F.RequestForm(
        data={"type": "other"},
        files={
            "attachment": _file(name="a.exe", content=b"abc", content_type="image/jpeg")
        },
    )
    assert not form_bad.is_valid()
    assert "attachment" in form_bad.errors


def test_request_form_attachment_magic_detects_mime_and_ext(monkeypatch):
    """
    Если mime определён (эмулируем через _sniff_mime), он должен быть из whitelist,
    и расширение тоже из whitelist.
    """
    from requests_app import forms as F

    # определяем как PDF — ок только с .pdf
    monkeypatch.setattr(F, "_sniff_mime", lambda f: "application/pdf")

    # валидный
    form_ok = F.RequestForm(
        data={"type": "other"},
        files={
            "attachment": _file(
                name="file.pdf",
                content=b"%PDF-1.4",
                content_type="application/octet-stream",
            )
        },
    )
    assert form_ok.is_valid()

    # неверное расширение при корректном mime
    form_bad = F.RequestForm(
        data={"type": "other"},
        files={
            "attachment": _file(
                name="file.png",
                content=b"%PDF-1.4",
                content_type="application/octet-stream",
            )
        },
    )
    assert not form_bad.is_valid()
    assert "attachment" in form_bad.errors


def test_request_form_attachment_size_limit(monkeypatch):
    from requests_app import forms as F

    # уменьшаем порог, чтобы не плодить большие буферы
    monkeypatch.setattr(F, "MAX_ATTACHMENT_SIZE", 5)
    big = SimpleUploadedFile("a.pdf", b"123456", content_type="application/pdf")
    form = F.RequestForm(data={"type": "other"}, files={"attachment": big})
    assert not form.is_valid()
    assert "attachment" in form.errors


# -------------------- RequestStatusForm --------------------


def test_status_form_requires_user_kwarg():
    from requests_app.forms import RequestStatusForm
    from requests_app.models import Request

    with pytest.raises(ValueError):
        RequestStatusForm(
            data={"status": Request.STATUS_APPROVED}, instance=Request(), user=None
        )


def test_status_form_allowed_statuses_by_role(user, hr_user):
    from requests_app.forms import RequestStatusForm
    from requests_app.models import Request

    # non-staff: только approved/rejected
    form_user = RequestStatusForm(user=user, instance=Request())
    values_user = {v for v, _ in form_user.fields["status"].choices}
    assert values_user == {Request.STATUS_APPROVED, Request.STATUS_REJECTED}

    # staff/HR: плюс cancelled
    form_hr = RequestStatusForm(user=hr_user, instance=Request())
    values_hr = {v for v, _ in form_hr.fields["status"].choices}
    assert values_hr == {
        Request.STATUS_APPROVED,
        Request.STATUS_REJECTED,
        Request.STATUS_CANCELLED,
    }


def test_status_form_clean_status_disallowed_for_role_raises(user):
    from requests_app.forms import RequestStatusForm
    from requests_app.models import Request

    form = RequestStatusForm(
        data={"status": Request.STATUS_CANCELLED}, user=user, instance=Request()
    )
    assert not form.is_valid()
    assert "status" in form.errors


def test_status_form_cannot_change_final_status(hr_user):
    from requests_app.forms import RequestStatusForm
    from requests_app.models import Request

    # финальная заявка
    r = Request(status=Request.STATUS_APPROVED)
    form = RequestStatusForm(
        data={"status": Request.STATUS_REJECTED}, user=hr_user, instance=r
    )
    assert not form.is_valid()
    assert "status" in form.errors


def test_status_form_clean_attachment_uses_common_validator(monkeypatch, hr_user):
    from requests_app import forms as F
    from requests_app.models import Request

    called = {"ok": False}

    def _spy(self, f):  # signature совпадает с методом
        called["ok"] = True

    monkeypatch.setattr(
        F.RequestForm, "_validate_attachment_common", _spy, raising=True
    )

    form = F.RequestStatusForm(
        data={"status": Request.STATUS_APPROVED},
        files={
            "attachment": _file(
                name="x.pdf", content=b"pdf", content_type="application/pdf"
            )
        },
        user=hr_user,
        instance=Request(),
    )
    # валидность не важна — нам важно, что вызвался общий валидатор
    form.is_valid()
    assert called["ok"] is True
