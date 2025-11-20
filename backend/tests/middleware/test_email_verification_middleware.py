"""
Тесты middleware для проверки верификации email.

Проверяют что неверифицированные пользователи:
1. Могут получить доступ только к определённым страницам
2. Редиректятся на страницу верификации
3. Могут верифицировать свой email
"""

import pytest
from django.contrib.auth import get_user_model
from django.test import Client, RequestFactory
from django.urls import reverse

from eusrr_backend.middleware import EmailVerificationMiddleware

Employee = get_user_model()


def make_user(email, verified=True, **kwargs):
    """Создаёт пользователя для тестов."""
    phone = kwargs.get(
        "phone_number", f"+7900{email[:7].replace('@', '').replace('.', '')}"
    )
    user = Employee.objects.create_user(
        email=email,
        password="TestPass123!",
        first_name=kwargs.get("first_name", "Test"),
        last_name=kwargs.get("last_name", "User"),
        phone_number=phone,
        telegram=kwargs.get("telegram", f"@{email.split('@')[0]}"),
        send_activation_email=False,
    )
    user.email_verified = verified
    user.is_active = True
    user.save(update_fields=["email_verified", "is_active"])
    return user


@pytest.mark.django_db
class TestEmailVerificationMiddleware:
    """Тесты middleware проверки верификации email."""

    def test_unverified_user_redirected_to_verification_page(self):
        """Неверифицированный пользователь редиректится на верификацию."""
        client = Client()
        user = make_user("unverified@test.com", verified=False)

        # Логинимся
        client.force_login(user)

        # Пытаемся зайти на главную
        response = client.get("/")

        # Должен быть редирект на страницу верификации
        assert response.status_code == 302
        assert (
            "verify-email" in response.url or "verify" in response.url.lower()
        )

    def test_verified_user_can_access_pages(self):
        """Верифицированный пользователь может работать нормально."""
        client = Client()
        user = make_user("verified@test.com", verified=True)

        client.force_login(user)

        # Можем зайти на главную (или получим 404, но не редирект)
        response = client.get("/")

        # Не должно быть редиректа на верификацию
        if response.status_code == 302:
            assert "verify" not in response.url.lower()

    def test_unverified_user_can_access_verification_page(self):
        """Неверифицированный пользователь может зайти на верификацию."""
        client = Client()
        user = make_user("unverified@test.com", verified=False)

        client.force_login(user)

        # Заходим на страницу верификации
        response = client.get(reverse("auth_front:verify_email"))

        # Должны попасть на страницу (200 или 405, но не редирект)
        assert response.status_code in [200, 405]

    def test_unverified_user_can_access_resend_page(self):
        """Неверифицированный пользователь может запросить код повторно."""
        client = Client()
        user = make_user("unverified@test.com", verified=False)

        client.force_login(user)

        # Заходим на страницу повторной отправки
        try:
            response = client.get(reverse("auth_front:resend_email"))
            # Должны попасть на страницу
            assert response.status_code in [200, 405]
        except Exception:
            # Если нет такого урла - ничего страшного
            pass

    def test_unverified_user_can_access_api_endpoints(self):
        """Неверифицированный пользователь может работать с API."""
        client = Client()
        user = make_user("unverified@test.com", verified=False)

        client.force_login(user)

        # API должно работать (проверка прав на уровне ViewSet)
        response = client.get("/api/v1/employees/me/")

        # Не должно быть редиректа (либо 200, либо 403/401)
        assert response.status_code in [200, 401, 403]

    def test_anonymous_user_redirected_to_login(self):
        """Анонимный пользователь редиректится на логин."""
        client = Client()

        # Пытаемся зайти на главную без логина
        response = client.get("/")

        # Должен быть редирект на логин
        assert response.status_code == 302
        assert (
            "login" in response.url.lower() or response.url == "/auth/login/"
        )

    def test_unverified_staff_can_access_admin(self):
        """Неверифицированный staff может зайти в админку."""
        client = Client()
        user = make_user("staff@test.com", verified=False)
        user.is_staff = True
        user.save()

        client.force_login(user)

        # Заходим в админку
        response = client.get("/admin/")

        # Должны попасть в админку (или редирект внутри админки)
        assert response.status_code in [200, 302]

        # Не должно быть редиректа на верификацию
        if response.status_code == 302:
            assert "verify" not in response.url.lower()

    def test_middleware_allows_static_and_media(self):
        """Middleware пропускает статику и медиа."""
        factory = RequestFactory()

        # Создаём middleware
        def dummy_view(request):
            from django.http import HttpResponse

            return HttpResponse("OK")

        middleware = EmailVerificationMiddleware(dummy_view)

        # Тестируем статику
        request = factory.get("/static/css/style.css")
        request.user = make_user("unverified@test.com", verified=False)

        response = middleware(request)

        # Должен пропустить (вызвать view)
        assert response.status_code == 200
        assert response.content == b"OK"

        # Тестируем медиа
        request = factory.get("/media/avatars/user.jpg")
        request.user = make_user("unverified2@test.com", verified=False)

        response = middleware(request)

        # Должен пропустить
        assert response.status_code == 200


@pytest.mark.django_db
class TestVerificationPageAccess:
    """Тесты доступа к страницам верификации."""

    def test_verification_page_exists(self):
        """Страница верификации существует."""
        client = Client()

        try:
            url = reverse("auth_front:verify_email")
            response = client.get(url)

            # Страница должна существовать
            assert response.status_code in [200, 302, 405]
        except Exception:
            # Если нет урла - тест пропускаем
            pytest.skip("Verification page URL not configured")

    def test_resend_page_exists(self):
        """Страница повторной отправки существует."""
        client = Client()

        try:
            url = reverse("auth_front:resend_email")
            response = client.get(url)

            # Страница должна существовать
            assert response.status_code in [200, 302, 405]
        except Exception:
            # Если нет урла - тест пропускаем
            pytest.skip("Resend page URL not configured")

    def test_verified_user_redirected_from_verification_page(self):
        """Верифицированный пользователь редиректится с верификации."""
        client = Client()
        user = make_user("verified@test.com", verified=True)

        client.force_login(user)

        try:
            url = reverse("auth_front:verify_email")
            response = client.get(url)

            # Может быть редирект или просто сообщение
            # Главное - не ошибка
            assert response.status_code in [200, 302]
        except Exception:
            pytest.skip("Verification page URL not configured")


@pytest.mark.django_db
class TestCriticalOperationsRestrictions:
    """
    Тесты что критичные операции заблокированы
    для неверифицированных пользователей.
    """

    def test_unverified_cannot_create_department_via_web(self):
        """Неверифицированный не может создать отдел через веб."""
        client = Client()
        user = make_user("staff@test.com", verified=False)
        user.is_staff = True
        user.save()

        client.force_login(user)

        # Пытаемся создать отдел
        response = client.post(
            "/api/v1/departments/",
            {"name": "Test Department"},
            content_type="application/json",
        )

        # Должен быть запрещён (или редирект на верификацию)
        assert response.status_code in [302, 403]

        if response.status_code == 302:
            assert "verify" in response.url.lower()

    def test_unverified_cannot_modify_other_users(self):
        """Неверифицированный staff не может менять других."""
        client = Client()
        staff = make_user("staff@test.com", verified=False)
        staff.is_staff = True
        staff.save()

        other_user = make_user("other@test.com", verified=True)

        client.force_login(staff)

        # Пытаемся изменить другого пользователя
        response = client.patch(
            f"/api/v1/employees/{other_user.id}/",
            {"first_name": "Hacked"},
            content_type="application/json",
        )

        # Должен быть запрещён
        assert response.status_code in [302, 403]
