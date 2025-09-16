# backend/tests/api/v1/feed/test_feed_api.py
from __future__ import annotations

"""
Тесты API фида (посты, комментарии, лайки) под новую политику доступа:
- права на объекты отдела выдаются через роль внутри конкретного отдела;
- company-посты требуют глобальных модельных прав/статуса staff.
"""

from typing import Iterable, Optional, Tuple

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.urls import reverse
from employees.constants import DeptPerm
from employees.models import (
    Department,
    DepartmentPermission,
    DepartmentRole,
    EmployeeDepartment,
)
from feed.constants import TYPE_COMPANY, TYPE_DEPARTMENT
from feed.models import Comment, Post, PostLike
from rest_framework import status
from rest_framework.test import APIClient

User = get_user_model()

pytestmark = pytest.mark.django_db


# ------------------------ helpers ------------------------


def _ensure_permission(
    app_label: str, model: type, codename: str, name: Optional[str] = None
) -> Permission:
    """Возвращает Permission с указанным codename, создаёт при отсутствии.

    Примечание:
        app_label параметр сейчас не используется и нужен для унификации вызовов.

    Args:
        app_label (str): Игнорируется.
        model (type): Класс модели (для ContentType).
        codename (str): Код права (напр. 'publish_company_post').
        name (Optional[str]): Человекочитаемое имя права.

    Returns:
        Permission: Объект права.
    """
    ct = ContentType.objects.get_for_model(model)
    perm, _ = Permission.objects.get_or_create(
        content_type=ct,
        codename=codename,
        defaults={"name": name or codename.replace("_", " ").title()},
    )
    return perm


def _mk_dept(name: str = "Dept", *, head: Optional[User] = None) -> Department:
    """Создаёт отдел.

    Args:
        name (str): Название отдела.
        head (Optional[User]): Руководитель.

    Returns:
        Department: Созданный отдел.
    """
    return Department.objects.create(name=name, head=head)


def _ensure_dept_permission(code: str, name: str | None = None) -> DepartmentPermission:
    """Возвращает/создаёт DepartmentPermission с заданным кодом."""
    perm, _ = DepartmentPermission.objects.get_or_create(
        code=code,
        defaults={"name": name or code.replace("_", " ").title()},
    )
    return perm


def _give_dept_role_with_perms(user, dept, *, perm_codenames, role_name="Role"):
    """Создаёт роль отдела, вешает scoped_permissions и назначает пользователю."""
    role = DepartmentRole.objects.create(name=role_name, department=dept)
    for code in perm_codenames:
        dp = _ensure_dept_permission(code)
        role.scoped_permissions.add(
            dp
        )  # ⟵ ВАЖНО: scoped_permissions, не auth.Permission
    EmployeeDepartment.objects.create(
        employee=user, department=dept, role=role, is_active=True
    )
    return role


def _post_data(
    *, type_: str, title: str = "T", body: str = "B", dept: Optional[Department] = None
) -> dict:
    """Собирает payload для создания/изменения поста.

    Args:
        type_ (str): Тип поста (см. feed.constants).
        title (str): Заголовок.
        body (str): Тело.
        dept (Optional[Department]): Отдел для department-поста.

    Returns:
        dict: Данные для POST/PUT/PATCH запроса.
    """
    data = {"type": type_, "title": title, "body": body}
    if type_ == TYPE_DEPARTMENT:
        data["department"] = dept.id if dept else None
    return data


def _create_post(
    author: User, *, type_: str, dept: Optional[Department] = None, title: str = "T"
) -> Post:
    """Утилита создания поста напрямую (минуя API), чтобы подготовить данные.

    Args:
        author (User): Автор.
        type_ (str): Тип поста.
        dept (Optional[Department]): Отдел для department.
        title (str): Заголовок.

    Returns:
        Post: Созданный пост.
    """
    return Post.objects.create(
        author=author, type=type_, department=dept, title=title, body="B"
    )


# ------------------------ URL helpers ------------------------


@pytest.fixture
def urls():
    """Именованные URL-роуты фида.

    Returns:
        dict: Словарь с callables для detail/action.
    """
    return {
        "posts_list": reverse("api:v1:posts-list"),
        "post_detail": lambda pk: reverse("api:v1:posts-detail", args=[pk]),
        "post_pin": lambda pk: reverse("api:v1:posts-pin", args=[pk]),
        "post_unpin": lambda pk: reverse("api:v1:posts-unpin", args=[pk]),
        "post_like": lambda pk: reverse("api:v1:posts-like", args=[pk]),
        "post_unlike": lambda pk: reverse("api:v1:posts-unlike", args=[pk]),
        "comments_list": reverse("api:v1:comments-list"),
        "comment_detail": lambda pk: reverse("api:v1:comments-detail", args=[pk]),
    }


# ------------------------ fixtures (project-aware) ------------------------


@pytest.fixture
def make_user(user_factory):
    """Фабрика пользователей на основе проектной фикстуры.

    Returns:
        Callable[..., User]: Создатель пользователя.
    """

    def _mk(email: str, **extra) -> User:
        return user_factory(email=email, **extra)

    return _mk


@pytest.fixture
def auth():
    def _as(u: User) -> APIClient:
        c = APIClient()
        c.force_authenticate(user=u)
        return c
    return _as

# ------------------------ A. Аноним ------------------------


class TestAnonymousAccess:
    """A. Аноним: все эндпоинты → 401."""

    def test_all_unauth_401(self, api_client: APIClient, make_user, urls):
        """Проверяет, что анониму всё недоступно (401)."""
        author = make_user("a@example.com")
        dept = _mk_dept(head=author)
        p = _create_post(author, type_=TYPE_DEPARTMENT, dept=dept)

        assert (
            api_client.get(urls["posts_list"]).status_code
            == status.HTTP_401_UNAUTHORIZED
        )
        assert (
            api_client.get(urls["post_detail"](p.id)).status_code
            == status.HTTP_401_UNAUTHORIZED
        )
        assert (
            api_client.post(
                urls["posts_list"],
                _post_data(type_=TYPE_DEPARTMENT, dept=dept),
                format="json",
            ).status_code
            == 401
        )
        assert api_client.post(urls["post_like"](p.id), {}).status_code == 401
        assert api_client.get(urls["comments_list"]).status_code == 401
        assert (
            api_client.post(
                urls["comments_list"], {"post": p.id, "text": "hi"}, format="json"
            ).status_code
            == 401
        )


# ------------------------ B. Обычный пользователь ------------------------


class TestRegularUser:
    """B. Обычный аутентифицированный пользователь: чтение/коммент/лайки 2xx, посты отдела 403."""

    def test_read_and_interact_but_no_dept_post_rights(self, make_user, auth, urls):
        """GET list/detail → 200, комментарий и like/unlike → 200, CRUD dept-поста → 403."""
        u = make_user("u@example.com")
        a = make_user("a@example.com")
        dept = _mk_dept(head=a)
        client = auth(u)
        # подготовим пост для чтения/лайков
        post = _create_post(a, type_=TYPE_DEPARTMENT, dept=dept)

        # чтение
        assert client.get(urls["posts_list"]).status_code == 200
        assert client.get(urls["post_detail"](post.id)).status_code == 200

        # комментарий
        r = client.post(
            urls["comments_list"], {"post": post.id, "text": "hi"}, format="json"
        )
        assert r.status_code == 201
        # лайк/анлайк
        assert client.post(urls["post_like"](post.id), {}).status_code == 200
        assert client.post(urls["post_unlike"](post.id), {}).status_code == 200

        # попытки создать/менять/удалять dept-пост → 403
        assert (
            client.post(
                urls["posts_list"],
                _post_data(type_=TYPE_DEPARTMENT, dept=dept),
                format="json",
            ).status_code
            == 403
        )
        assert client.patch(
            urls["post_detail"](post.id), {"title": "X"}, format="json"
        ).status_code in (403, 404)
        assert client.delete(urls["post_detail"](post.id)).status_code in (403, 404)

        # pin/unpin недоступны
        assert client.post(urls["post_pin"](post.id)).status_code == 403
        assert client.post(urls["post_unpin"](post.id)).status_code == 403


# ------------------------ C. Роль в отделе ------------------------


class TestDepartmentRole:
    """C. Роль в отделе с perm 'manage_department_feed' даёт запись в своём отделе, но не в чужом."""

    PUBLISH_CODE = getattr(DeptPerm, "CREATE_POST", "publish_department_post")

    def test_create_update_delete_own_department(self, make_user, auth, urls):
        """В своём отделе → 201/200/204; в другом отделе → 403."""

        u = make_user("role@example.com")
        d1 = _mk_dept("D1")
        d2 = _mk_dept("D2")
        _give_dept_role_with_perms(
            u, d1,
            perm_codenames=[DeptPerm.CREATE_POST, DeptPerm.MANAGE_FEED]
        )

        client = auth(u)

        # create в своем отделе
        r = client.post(
            urls["posts_list"],
            _post_data(type_=TYPE_DEPARTMENT, dept=d1, title="R1"),
            format="json",
        )
        assert r.status_code == 201, r.content
        pid = r.json()["id"]

        # update/destroy своего поста
        assert (
            client.patch(
                urls["post_detail"](pid), {"title": "R1X"}, format="json"
            ).status_code
            == 200
        )
        assert client.delete(urls["post_detail"](pid)).status_code in (200, 204)

        # create в чужом отделе → 403
        r2 = client.post(
            urls["posts_list"],
            _post_data(type_=TYPE_DEPARTMENT, dept=d2, title="No"),
            format="json",
        )
        assert r2.status_code == 403


# ------------------------ D. Руководитель отдела ------------------------


class TestDepartmentHead:
    """D. Head: полные права на посты своего отдела."""

    def test_head_can_manage_department_posts(self, make_user, auth, urls):
        """head своего отдела может создавать/изменять/удалять dept-посты."""
        head = make_user("head@example.com")
        dept = _mk_dept("HD", head=head)
        client = auth(head)

        r = client.post(
            urls["posts_list"],
            _post_data(type_=TYPE_DEPARTMENT, dept=dept, title="H"),
            format="json",
        )
        assert r.status_code == 201
        pid = r.json()["id"]

        assert (
            client.patch(
                urls["post_detail"](pid), {"title": "HX"}, format="json"
            ).status_code
            == 200
        )
        assert client.delete(urls["post_detail"](pid)).status_code in (200, 204)


# ------------------------ E. staff/superuser и pin ------------------------


class TestStaffAndPinning:
    """E. Staff/superuser: полный доступ; pin/unpin доступны только staff."""

    def test_staff_full_access_and_pin(self, make_user, auth, urls):
        """staff: CRUD company/dept + pin/unpin."""
        staff = make_user("staff@example.com", staff=True)
        d = _mk_dept("PD")
        client = auth(staff)

        # company пост
        r = client.post(
            urls["posts_list"], _post_data(type_=TYPE_COMPANY, title="C"), format="json"
        )
        assert r.status_code == 201
        pid = r.json()["id"]

        # dept пост
        r2 = client.post(
            urls["posts_list"],
            _post_data(type_=TYPE_DEPARTMENT, dept=d, title="D"),
            format="json",
        )
        assert r2.status_code == 201
        pid2 = r2.json()["id"]

        # pin/unpin
        assert client.post(urls["post_pin"](pid)).status_code == 200
        assert client.post(urls["post_unpin"](pid)).status_code == 200

        # update/delete
        assert (
            client.patch(
                urls["post_detail"](pid2), {"title": "DX"}, format="json"
            ).status_code
            == 200
        )
        assert client.delete(urls["post_detail"](pid2)).status_code in (200, 204)


# ------------------------ F. Глобальные модельные права на company ------------------------


class TestCompanyModelPermsGranular:
    """Гранулярные проверки модельных прав для company-постов."""

    def test_company_create_requires_add_only(self, make_user, auth, urls):
        """Наличие только feed.add_post → create=201; update/delete без change/delete → 403."""
        u = make_user("only-add@example.com")
        client = auth(u)

        # даём только add_post
        u.user_permissions.add(
            _ensure_permission("feed", Post, "add_post", "Can add Post")
        )

        # create OK
        rc = client.post(
            urls["posts_list"], _post_data(type_=TYPE_COMPANY, title="C"), format="json"
        )
        assert rc.status_code == status.HTTP_201_CREATED, rc.content
        pid = rc.json()["id"]

        # update/delete запрещены (нет change/delete)
        assert (
            client.patch(
                urls["post_detail"](pid), {"title": "CX"}, format="json"
            ).status_code
            == 403
        )
        assert client.delete(urls["post_detail"](pid)).status_code == 403

    def test_company_update_requires_change_only(self, make_user, auth, urls):
        """Только feed.change_post → update=200; create без add и delete без delete → 403."""
        author = make_user("author@example.com")
        editor = make_user("only-change@example.com")
        client = auth(editor)

        # готовим пост напрямую, чтобы не требовать add_post у editor
        p = _create_post(author, type_=TYPE_COMPANY, title="C2")

        # даём только change_post
        editor.user_permissions.add(
            _ensure_permission("feed", Post, "change_post", "Can change Post")
        )

        # create запрещён (нет add_post)
        assert (
            client.post(
                urls["posts_list"],
                _post_data(type_=TYPE_COMPANY, title="NC"),
                format="json",
            ).status_code
            == 403
        )

        # update OK
        assert (
            client.patch(
                urls["post_detail"](p.id), {"title": "C2X"}, format="json"
            ).status_code
            == 200
        )

        # delete запрещён (нет delete_post)
        assert client.delete(urls["post_detail"](p.id)).status_code == 403

    def test_company_delete_requires_delete_only(self, make_user, auth, urls):
        """Только feed.delete_post → delete=204; create/update без add/change → 403/403."""
        author = make_user("author@example.com")
        deleter = make_user("only-delete@example.com")
        client = auth(deleter)

        p = _create_post(author, type_=TYPE_COMPANY, title="C3")

        # даём только delete_post
        deleter.user_permissions.add(
            _ensure_permission("feed", Post, "delete_post", "Can delete Post")
        )

        # create/update запрещены
        assert (
            client.post(
                urls["posts_list"],
                _post_data(type_=TYPE_COMPANY, title="NC"),
                format="json",
            ).status_code
            == 403
        )
        assert (
            client.patch(
                urls["post_detail"](p.id), {"title": "C3X"}, format="json"
            ).status_code
            == 403
        )

        # delete OK
        resp = client.delete(urls["post_detail"](p.id))
        assert resp.status_code in (200, 204)

    def test_company_perms_do_not_grant_department(self, make_user, auth, urls):
        """Модельные права на Post НЕ дают права создавать department-посты."""
        u = make_user("model-perms@example.com")
        client = auth(u)

        # дадим все три модельных права — всё равно dept должен быть 403
        u.user_permissions.add(
            _ensure_permission("feed", Post, "add_post", "Can add Post"),
            _ensure_permission("feed", Post, "change_post", "Can change Post"),
            _ensure_permission("feed", Post, "delete_post", "Can delete Post"),
        )

        d = _mk_dept("DeptX")
        assert (
            client.post(
                urls["posts_list"],
                _post_data(type_=TYPE_DEPARTMENT, dept=d, title="D"),
                format="json",
            ).status_code
            == 403
        )


# ------------------------ G. Комментарии ------------------------


class TestComments:
    """G. Комментарии: создание любым аутентифицированным; изменение — автор/staff."""

    def test_create_and_update_delete_policies(self, make_user, auth, urls):
        """Создание: 201; редактирование/удаление: автор/staff."""
        author = make_user("a@example.com")
        reader = make_user("r@example.com")
        staff = make_user("s@example.com", staff=True)

        dept = _mk_dept()
        post = _create_post(author, type_=TYPE_DEPARTMENT, dept=dept)

        # reader создаёт комментарий
        client_r = auth(reader)
        rc = client_r.post(
            urls["comments_list"], {"post": post.id, "text": "hi"}, format="json"
        )
        assert rc.status_code == 201
        cid = rc.json()["id"]

        # чужой юзер менять не может
        other = make_user("o@example.com")
        client_o = auth(other)
        assert (
            client_o.patch(
                urls["comment_detail"](cid), {"text": "hack"}, format="json"
            ).status_code
            == 403
        )
        assert client_o.delete(urls["comment_detail"](cid)).status_code == 403

        # автор может
        resp = client_r.patch(urls["comment_detail"](cid), {"text": "ok"}, format="json")
        assert resp.status_code == 200
        assert resp.json().get("text") == "ok" 
        # staff может
        client_s = auth(staff)
        del_resp = client_s.delete(urls["comment_detail"](cid))
        assert del_resp.status_code in (200, 204)
        # после удаления — 404
        get_after_del = client_r.get(urls["comment_detail"](cid))
        assert get_after_del.status_code == 404


# ------------------------ H. Лайки (идемпотентность и is_liked) ------------------------


class TestLikes:
    """H. Лайки: идемпотентность и синхронизация is_liked."""

    def test_like_unlike_idempotent_and_reflected(self, make_user, auth, urls):
        """Повторный like/unlike не искажает счётчик; поле is_liked корректно отражается в detail."""
        a = make_user("a@example.com")
        u = make_user("u@example.com")
        dept = _mk_dept()
        post = _create_post(a, type_=TYPE_DEPARTMENT, dept=dept)

        client = auth(u)

        # старт: не лайкнуто
        d0 = client.get(urls["post_detail"](post.id)).json()
        assert d0.get("is_liked") in (False, None)

        # первый like увеличивает счётчик
        r1 = client.post(urls["post_like"](post.id), {})
        assert r1.status_code == 200
        liked1 = r1.json().get("liked")
        assert liked1 is True

        # повторный like не увеличивает
        r2 = client.post(urls["post_like"](post.id), {})
        assert r2.status_code == 200

        # detail отражает is_liked=True
        d1 = client.get(urls["post_detail"](post.id)).json()
        assert d1.get("is_liked") is True

        # unlike уменьшает, повторный не уводит < 0
        r3 = client.post(urls["post_unlike"](post.id), {})
        assert r3.status_code == 200 and r3.json().get("liked") is False
        r4 = client.post(urls["post_unlike"](post.id), {})
        assert r4.status_code == 200

        d2 = client.get(urls["post_detail"](post.id)).json()
        assert d2.get("is_liked") in (False, None)


# ------------------------ I. Негативные кейсы валидации ------------------------


class TestValidation:
    """I. Негативные кейсы: отсутствие department, запрет чужого отдела и т.п."""

    def test_department_type_requires_department_field(self, make_user, auth, urls):
        """type=department без department → 400."""
        u = make_user("u@example.com")
        client = auth(u)
        r = client.post(
            urls["posts_list"],
            _post_data(type_=TYPE_DEPARTMENT, dept=None),
            format="json",
        )
        assert r.status_code == 400

    def test_cannot_create_in_other_department_with_role(self, make_user, auth, urls):
        """Роль в одном отделе не даёт создании в другом отделе → 403."""
        u = make_user("u@example.com")
        d1 = _mk_dept("D1")
        d2 = _mk_dept("D2")
        _give_dept_role_with_perms(u, d1, perm_codenames=["publish_department_post"])
        client = auth(u)
        r = client.post(
            urls["posts_list"],
            _post_data(type_=TYPE_DEPARTMENT, dept=d2),
            format="json",
        )
        assert r.status_code == 403


def test_company_create_forbidden_for_regular_user(make_user, auth, urls):
    u = make_user("regular@example.com")
    client = auth(u)
    resp = client.post(
        urls["posts_list"],
        {"type": "company", "title": "X", "body": "B"},
        format="json",
    )
    assert resp.status_code == 403
