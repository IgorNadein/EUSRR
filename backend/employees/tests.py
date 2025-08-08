import io
from PIL import Image
from django.test import TestCase, Client, override_settings
from django.urls import reverse
from unittest.mock import patch
from django.core.files.uploadedfile import SimpleUploadedFile
from employees.models import Employee
from phonenumber_field.phonenumber import to_python


def fake_send_sms(phone, text, sender="EUSRR"):
    print(f"FAKE SMS: {phone}: {text}")
    return {"status": "success", "data": []}


@override_settings(AUTH_USER_MODEL="employees.Employee")
class RegistrationTestCase(TestCase):
    def setUp(self):
        self.client = Client()

    def _valid_avatar(self):
        img_io = io.BytesIO()
        img = Image.new("RGB", (10, 10), color=(255, 0, 0))
        img.save(img_io, format="JPEG")
        img_io.seek(0)
        return SimpleUploadedFile("test.jpg", img_io.read(), content_type="image/jpeg")

    @patch("employees.views_front.send_sms_alpha", side_effect=fake_send_sms)
    def test_register_and_sms_sent(self, mock_send_sms):
        url = reverse("register")
        data = {
            "phone_number": "+79991112233",
            "first_name": "Иван",
            "last_name": "Иванов",
            "patronymic": "",
            "birth_date": "",
            "email": "ivanov@example.com",
            "whatsapp": "",
            "telegram": "@testuser",
            "wechat": "",
            "avatar": self._valid_avatar(),
            "password1": "MyPassw0rd!23",
            "password2": "MyPassw0rd!23",
        }
        response = self.client.post(url, data, follow=True)
        self.assertTrue(Employee.objects.filter(email="ivanov@example.com").exists())
        user = Employee.objects.get(email="ivanov@example.com")
        self.assertFalse(user.is_active)
        self.assertIsNotNone(user.sms_activation_code)
        mock_send_sms.assert_called_once()
        if response.context and "form" in response.context:
            self.assertFalse(response.context["form"].errors)
        self.assertIn(response.status_code, [200, 302])

    def test_register_with_invalid_avatar(self):
        url = reverse("register")
        avatar = SimpleUploadedFile(
            "bad.txt", b"not an image", content_type="text/plain"
        )
        data = {
            "phone_number": "+79991112244",
            "first_name": "Алексей",
            "last_name": "Алексеев",
            "patronymic": "",
            "birth_date": "",
            "email": "alexey@example.com",
            "whatsapp": "",
            "telegram": "@tester",
            "wechat": "",
            "avatar": avatar,
            "password1": "MyPassw0rd!23",
            "password2": "MyPassw0rd!23",
        }
        response = self.client.post(url, data, follow=True)
        self.assertIn("avatar", response.context["form"].errors)

    def test_register_without_contacts(self):
        url = reverse("register")
        data = {
            "phone_number": "+79991112277",
            "first_name": "Безконтактный",
            "last_name": "Пользователь",
            "patronymic": "",
            "birth_date": "",
            "email": "no-contacts@example.com",
            "whatsapp": "",
            "telegram": "",
            "wechat": "",
            "avatar": self._valid_avatar(),
            "password1": "MyPassw0rd!23",
            "password2": "MyPassw0rd!23",
        }
        response = self.client.post(url, data, follow=True)
        self.assertIn("__all__", response.context["form"].errors)
        self.assertIn(
            "Заполните хотя бы одно из полей",
            str(response.context["form"].errors["__all__"]),
        )

    def test_register_duplicate_email(self):
        Employee.objects.create_user(
            phone_number="+79990000001",
            email="dup@example.com",
            first_name="Test",
            last_name="Dup",
            password="12345678",
            telegram="@dup",
        )
        url = reverse("register")
        data = {
            "phone_number": "+79990000002",
            "first_name": "Другой",
            "last_name": "Пользователь",
            "patronymic": "",
            "birth_date": "",
            "email": "dup@example.com",  # duplicate
            "whatsapp": "",
            "telegram": "@other",
            "wechat": "",
            "avatar": self._valid_avatar(),
            "password1": "MyPassw0rd!23",
            "password2": "MyPassw0rd!23",
        }
        response = self.client.post(url, data, follow=True)
        self.assertIn("email", response.context["form"].errors)

    def test_register_duplicate_phone(self):
        Employee.objects.create_user(
            phone_number="+79995554444",
            email="phone1@example.com",
            first_name="Phone",
            last_name="Dup",
            password="12345678",
            telegram="@dup",
        )
        url = reverse("register")
        data = {
            "phone_number": "+79995554444",  # duplicate
            "first_name": "Phone2",
            "last_name": "Dup2",
            "patronymic": "",
            "birth_date": "",
            "email": "phone2@example.com",
            "whatsapp": "",
            "telegram": "@other",
            "wechat": "",
            "avatar": self._valid_avatar(),
            "password1": "MyPassw0rd!23",
            "password2": "MyPassw0rd!23",
        }
        response = self.client.post(url, data, follow=True)
        self.assertIn("phone_number", response.context["form"].errors)

    def test_sms_code_verify(self):
        user = Employee.objects.create_user(
            phone_number="+79991112234",
            email="test2@example.com",
            first_name="Петр",
            last_name="Петров",
            password="Testpassw0rd!",
            telegram="@testuser",
        )
        user.is_active = False
        user.sms_activation_code = "123456"
        user.save()

        session = self.client.session
        session["phone_number"] = str(user.phone_number)
        session.save()

        # Верный код
        response = self.client.post(
            reverse("sms_verify"), {"code": "123456"}, follow=False
        )
        user = Employee.objects.get(phone_number=to_python("+79991112234"))
        user.refresh_from_db()
        self.assertTrue(user.is_active)
        self.assertIsNone(user.sms_activation_code)
        self.assertIn(response.status_code, [200, 302])

        # Неверный код
        user.is_active = False
        user.sms_activation_code = "654321"
        user.save()
        session = self.client.session
        session["phone_number"] = str(user.phone_number)
        session.save()
        response = self.client.post(
            reverse("sms_verify"), {"code": "000000"}, follow=False
        )
        self.assertIn("Код неверный", response.content.decode())
        user.refresh_from_db()
        self.assertFalse(user.is_active)

    def test_sms_verify_session_expired(self):
        # Если нет номера в сессии — должен быть редирект на регистрацию
        response = self.client.get(reverse("sms_verify"), follow=True)
        self.assertIn(response.status_code, [200, 302])
        redirect_urls = [url for url, code in response.redirect_chain]
        self.assertTrue(
            any(
                reverse("register") in url or reverse("login") in url
                for url in redirect_urls
            ),
            f"Chain was: {redirect_urls}",
        )

    def test_register_invalid_password(self):
        url = reverse("register")
        data = {
            "phone_number": "+79990002233",
            "first_name": "Pass",
            "last_name": "Fail",
            "patronymic": "",
            "birth_date": "",
            "email": "passfail@example.com",
            "whatsapp": "",
            "telegram": "@pfail",
            "wechat": "",
            "avatar": self._valid_avatar(),
            "password1": "short",  # too short/simple
            "password2": "short",
        }
        response = self.client.post(url, data, follow=True)
        self.assertIn("password2", response.context["form"].errors)
        self.assertTrue(
            any(
                "слишком короткий" in err or "short" in err.lower()
                for err in response.context["form"].errors["password2"]
            )
        )

    def test_register_password_mismatch(self):
        url = reverse("register")
        data = {
            "phone_number": "+79990002234",
            "first_name": "Mismatch",
            "last_name": "Pass",
            "patronymic": "",
            "birth_date": "",
            "email": "mismatch@example.com",
            "whatsapp": "",
            "telegram": "@mmfail",
            "wechat": "",
            "avatar": self._valid_avatar(),
            "password1": "MyPassw0rd!23",
            "password2": "OtherPassw0rd!23",
        }
        response = self.client.post(url, data, follow=True)
        self.assertIn("password2", response.context["form"].errors)
        self.assertTrue(
            any(
                "не совпадают" in err or "mismatch" in err.lower()
                for err in response.context["form"].errors["password2"]
            )
        )
