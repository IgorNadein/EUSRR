from common.emails import send_templated_mail
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from django.utils.crypto import get_random_string
from employees.models import Employee
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import EmailSerializer, EmailVerifySerializer, RegisterSerializer

# опциональная нормализация телефона
try:
    import phonenumbers
    from phonenumbers import PhoneNumberFormat
except Exception:
    phonenumbers = None
    PhoneNumberFormat = None


class ResendEmailAPIView(APIView):
    """
    POST /api/v1/auth/resend-email/
    body: {"email": "user@ex.com"}
    """

    throttle_scope = "anon"

    def post(self, request):
        ser = EmailSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        email = ser.validated_data["email"]

        user = Employee.objects.filter(email__iexact=email).first()
        if not user:
            return Response({"ok": False, "error": "user_not_found"}, status=404)

        if user.email_verified:
            return Response({"ok": False, "error": "already_verified"}, status=400)

        # простая частотная защита по времени отправки в сессии оставим во вьюхе фронта,
        # на API уровне можно дополнить throttle/ratelimit на IP
        user.email_activation_code = get_random_string(6, "0123456789")
        user.save(update_fields=["email_activation_code"])

        send_templated_mail(
            subject="Подтверждение регистрации",
            to=[user.email],
            template_base="emails/registration_verify_code",
            context={"code": user.email_activation_code, "user": user},
        )
        return Response({"ok": True}, status=200)


class VerifyEmailAPIView(APIView):
    throttle_scope = "anon"

    def post(self, request):
        ser = EmailVerifySerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        email = ser.validated_data["email"]
        code = ser.validated_data["code"].strip()

        user = Employee.objects.filter(email__iexact=email).first()
        if not user:
            return Response({"ok": False, "error": "user_not_found"}, status=404)
        if not code:
            return Response({"ok": False, "error": "empty_code"}, status=400)

        if user.verify_email(code):  # внутри должна ставиться is_active=True
            return Response({"ok": True, "user_id": user.id}, status=200)

        return Response({"ok": False, "error": "invalid_code"}, status=400)


def _normalize_phone(raw: str) -> str | None:
    if not raw:
        return None
    if phonenumbers is None:
        return raw.strip()
    region = getattr(settings, "PHONE_DEFAULT_REGION", "RU")
    try:
        pn = phonenumbers.parse(str(raw), region)
        if not phonenumbers.is_valid_number(pn):
            return None
        return phonenumbers.format_number(pn, PhoneNumberFormat.E164)
    except Exception:
        return None


def _detect_phone_field() -> str | None:
    for n in ("phone", "phone_number", "mobile", "msisdn", "tel"):
        if any(f.name == n for f in Employee._meta.fields):
            return n
    return None


PHONE_FIELD = _detect_phone_field()


class RegisterAPIView(APIView):
    """
    POST /api/v1/auth/register/
    body: {email, password, first_name?, last_name?, phone?}

    Поведение:
      - если email уже подтверждён → 400 email_taken
      - если пользователь есть, но не подтверждён → перегенерируем код и шлём письмо (ok + resent=True)
      - если нет пользователя → создаём, is_active=False, отправляем код (ok)
    """

    throttle_scope = "anon"

    @transaction.atomic
    def post(self, request):
        ser = RegisterSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        v = ser.validated_data

        email = v["email"].strip().lower()
        password = v["password"]

        user = Employee.objects.filter(email__iexact=email).first()
        if user and user.email_verified:
            return Response({"ok": False, "error": "email_taken"}, status=400)

        if user and not user.email_verified:
            user.email_activation_code = get_random_string(6, "0123456789")
            user.is_active = False
            user.set_password(
                password
            )  # обновим пароль, если вдруг был пустой/тестовый
            if PHONE_FIELD and v.get("phone"):
                norm = _normalize_phone(v["phone"])
                if norm:
                    setattr(user, PHONE_FIELD, norm)
            if v.get("first_name"):
                user.first_name = v["first_name"]
            if v.get("last_name"):
                user.last_name = v["last_name"]
            user.save()
            send_templated_mail(
                subject="Подтверждение регистрации",
                to=[user.email],
                template_base="emails/registration_verify_code",
                context={"code": user.email_activation_code, "user": user},
            )
            return Response({"ok": True, "resent": True}, status=200)

        # создаём нового
        user = Employee(
            email=email,
            first_name=v.get("first_name", ""),
            last_name=v.get("last_name", ""),
            email_verified=False,
            is_active=False,
            email_activation_code=get_random_string(6, "0123456789"),
        )
        if PHONE_FIELD and v.get("phone"):
            norm = _normalize_phone(v["phone"])
            if norm:
                setattr(user, PHONE_FIELD, norm)
        user.set_password(password)
        user.save()

        send_templated_mail(
            subject="Подтверждение регистрации",
            to=[user.email],
            template_base="emails/registration_verify_code",
            context={"code": user.email_activation_code, "user": user},
        )
        return Response({"ok": True}, status=201)
