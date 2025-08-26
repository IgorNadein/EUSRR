# tests/feed/test_models.py
import io
import pytest
from django.utils import timezone
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from django.core.exceptions import ValidationError

from employees.models import Employee, Department
from feed.models import Post, Comment, PostLike
from feed.constants import TYPE_COMPANY, TYPE_DEPARTMENT, TYPE_EMPLOYEE

# ---------- helpers ----------

_seq = 1
def _uniq_email(prefix="u"):
    global _seq
    _seq += 1
    return f"{prefix}{_seq}@example.com"

def _uniq_phone():
    global _seq
    _seq += 1
    return f"+7999{_seq:07d}"

def _user(**kwargs) -> Employee:
    u = Employee.objects.create_user(
        email=_uniq_email(),
        password="pass",
        phone_number=_uniq_phone(),
        send_activation_email=False,
        first_name="T",
        last_name="U",
    )
    if kwargs:
        for k, v in kwargs.items():
            setattr(u, k, v)
        u.save()
    return u

def _img_file(name="p.png"):
    # простой валидный файл для ImageField
    return SimpleUploadedFile(name, b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR", content_type="image/png")

def _bin_file(name="a.txt"):
    return SimpleUploadedFile(name, b"hello", content_type="text/plain")


# ---------- Post ----------

@pytest.mark.django_db
def test_post_department_constraints():
    author = _user()
    dept = Department.objects.create(name="QA")

    # type=department без department -> IntegrityError
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Post.objects.create(author=author, type=TYPE_DEPARTMENT, title="t", body="b")

    # type!=department с указанным department -> IntegrityError
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Post.objects.create(author=author, type=TYPE_EMPLOYEE, department=dept, title="t", body="b")

    # валидные кейсы
    p1 = Post.objects.create(author=author, type=TYPE_DEPARTMENT, department=dept, title="t1", body="b1")
    p2 = Post.objects.create(author=author, type=TYPE_EMPLOYEE, title="t2", body="b2")
    p3 = Post.objects.create(author=author, type=TYPE_COMPANY, title="t3", body="b3")
    assert p1.department_id == dept.id
    assert p2.department_id is None
    assert p3.department_id is None


@pytest.mark.django_db
def test_post_on_delete_protect_department():
    author = _user()
    dept = Department.objects.create(name="R&D")
    Post.objects.create(author=author, type=TYPE_DEPARTMENT, department=dept, title="news", body="text")
    # отдел нельзя удалить — PROTECT
    with pytest.raises(ProtectedError):
        dept.delete()


@pytest.mark.django_db
def test_post_likes_count_non_negative_constraint():
    author = _user()
    # Попытка создать пост с отрицательным счётчиком — нарушает CheckConstraint
    with pytest.raises(IntegrityError):
        Post.objects.create(author=author, type=TYPE_EMPLOYEE, title="bad", body="b", likes_count=-1)


@pytest.mark.django_db
def test_post_ordering_pinned_then_created_at():
    author = _user()
    p1 = Post.objects.create(author=author, type=TYPE_EMPLOYEE, title="1", body="b", pinned=False)
    p2 = Post.objects.create(author=author, type=TYPE_EMPLOYEE, title="2", body="b", pinned=True)
    p3 = Post.objects.create(author=author, type=TYPE_EMPLOYEE, title="3", body="b", pinned=False)
    # задаём явные времена, чтобы проверить сортировку по created_at ↓
    now = timezone.now()
    Post.objects.filter(pk=p1.pk).update(created_at=now - timezone.timedelta(minutes=2))
    Post.objects.filter(pk=p2.pk).update(created_at=now - timezone.timedelta(minutes=1))
    Post.objects.filter(pk=p3.pk).update(created_at=now - timezone.timedelta(minutes=3))

    ids = list(Post.objects.values_list("id", flat=True))
    # Сначала закреплённые (pinned=True), внутри — по created_at ↓, затем обычные — тоже по created_at ↓
    # Здесь: p2 (pinned), потом p1 (новее p3), потом p3
    assert ids == [p2.id, p1.id, p3.id]


@pytest.mark.django_db
def test_post_str_variants():
    author = _user()
    dept = Department.objects.create(name="Ops")
    p_company = Post.objects.create(author=author, type=TYPE_COMPANY, title="Company news", body="b")
    p_dept = Post.objects.create(author=author, type=TYPE_DEPARTMENT, department=dept, title="Dept news", body="b")
    p_emp = Post.objects.create(author=author, type=TYPE_EMPLOYEE, title="Personal", body="b")

    assert str(p_company).startswith("[Компания]")
    assert f"[Отдел: {dept}]" in str(p_dept)
    assert "[Сотрудник:" in str(p_emp)


# ---------- PostLike ----------

@pytest.mark.django_db
def test_postlike_unique_per_user_and_post():
    u = _user()
    p = Post.objects.create(author=u, type=TYPE_EMPLOYEE, title="t", body="b")

    PostLike.objects.create(post=p, user=u)
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            PostLike.objects.create(post=p, user=u)

    # __str__
    assert "❤" in str(PostLike.objects.first())


# ---------- Comment ----------

@pytest.mark.django_db
def test_comment_requires_text_or_file_or_image():
    u = _user()
    p = Post.objects.create(author=u, type=TYPE_EMPLOYEE, title="t", body="b")

    # только текст -> ок
    c1 = Comment.objects.create(post=p, author=u, text="hi")
    assert c1.pk

    # только изображение -> ок
    c2 = Comment.objects.create(post=p, author=u, image=_img_file())
    assert c2.pk and c2.text == ""

    # только файл -> ок
    c3 = Comment.objects.create(post=p, author=u, attachment=_bin_file())
    assert c3.pk and c3.text == ""

    # пусто всё -> нарушает CheckConstraint
    with pytest.raises((IntegrityError, ValidationError)):
        with transaction.atomic():
            c = Comment(post=p, author=u, text="")
            c.full_clean()
            c.save()

@pytest.mark.django_db
def test_comment_ordering_by_created_at():
    u = _user()
    p = Post.objects.create(author=u, type=TYPE_EMPLOYEE, title="t", body="b")
    c1 = Comment.objects.create(post=p, author=u, text="a")
    c2 = Comment.objects.create(post=p, author=u, text="b")

    # Переставим created_at, чтобы проверить ordering ASC
    now = timezone.now()
    Comment.objects.filter(pk=c1.pk).update(created_at=now - timezone.timedelta(minutes=2))
    Comment.objects.filter(pk=c2.pk).update(created_at=now - timezone.timedelta(minutes=1))

    ordered = list(p.comments.values_list("id", flat=True))
    assert ordered == [c1.id, c2.id]
