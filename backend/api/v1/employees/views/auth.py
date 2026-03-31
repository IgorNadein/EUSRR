"""Auth-related views.

Регистрация, подтверждение email и повторная отправка кода.
"""

from __future__ import annotations

import logging
from datetime import timedelta

from common.emails import send_templated_mail
from drf_spectacular.utils import OpenApiResponse, extend_schema, inline_serializer
from django.core.files.base import ContentFile
from django.db import transaction
from django.utils import timezone
from django.utils.crypto import get_random_string
from employees.models import Position, Skill
from employees.utils import _normalize_phone
from rest_framework import serializers, status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from ..serializers import (EmailSerializer, EmailVerifySerializer,
                           RegisterSerializer)
from ._helpers import Employee
from .mixins import LdapUserCreationMixin

logger = logging.getLogger(__name__)


class AnonymousAPIView(APIView):
    """Базовый класс для анонимных (публичных) API endpoints.
    
    Все auth-related views наследуются от этого класса для DRY.
    Используется только JWT (без SessionAuthentication) → CSRF не требуется.
    """
    authentication_classes = []  # Отключаем SessionAuthentication для публичных endpoints
    throttle_scope = "anon"
    permission_classes = [AllowAny]


class ResendEmailAPIView(AnonymousAPIView):
    """POST /api/v1/auth/resend-email/  body: {"email": "..."}"""

    @extend_schema(
        tags=["Auth"],
        summary="Повторно отправить код подтверждения email",
        request=EmailSerializer,
        responses={
            200: inline_serializer(
                "ResendEmailResponse",
                {"ok": serializers.BooleanField()},
            ),
            400: OpenApiResponse(description="Email уже подтвержден."),
            404: OpenApiResponse(description="Пользователь не найден."),
        },
    )
    def post(self, request):
        ser = EmailSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        email = ser.validated_data["email"]

        user = Employee.objects.filter(email__iexact=email).first()
        if not user:
            return Response({"ok": False, "error": "user_not_found"}, status=404)
        if user.email_verified:
            return Response({"ok": False, "error": "already_verified"}, status=400)

        user.email_activation_code = get_random_string(6, "0123456789")
        user.save(update_fields=["email_activation_code"])

        send_templated_mail(
            subject="Подтверждение регистрации",
            to=[user.email],
            template_base="emails/registration_verify_code",
            context={"code": user.email_activation_code, "user": user},
        )
        return Response({"ok": True}, status=200)


class VerifyEmailAPIView(AnonymousAPIView):
    @extend_schema(
        tags=["Auth"],
        summary="Подтвердить email кодом",
        request=EmailVerifySerializer,
        responses={
            200: inline_serializer(
                "VerifyEmailResponse",
                {
                    "ok": serializers.BooleanField(),
                    "user_id": serializers.IntegerField(),
                },
            ),
            400: OpenApiResponse(description="Код пустой, неверный или истек."),
            404: OpenApiResponse(description="Пользователь не найден."),
        },
    )
    def post(self, request):
        """Подтверждает email и активирует пользователя.
        
        Активация синхронизируется в LDAP через сигналы.
        """
        ser = EmailVerifySerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        email = ser.validated_data["email"].strip().lower()
        code = ser.validated_data["code"].strip()

        user = Employee.objects.filter(email__iexact=email).first()
        if not user:
            return Response({"ok": False, "error": "user_not_found"}, status=404)
        if not code:
            return Response({"ok": False, "error": "empty_code"}, status=400)

        created = getattr(user, "created_at", None) or getattr(
            user, "date_joined", None
        )
        if created and not user.email_verified:
            if timezone.now() - created > timedelta(minutes=5):
                user.delete()
                return Response({"ok": False, "error": "expired"}, status=400)

        if not user.verify_email(code):
            return Response({"ok": False, "error": "invalid_code"}, status=400)

        # Активируем пользователя (сигнал sync_employee_to_ldap_on_save синхронизирует в LDAP)
        user.is_active = True
        user._ldap_changes = {"is_active": True}
        user.save()

        return Response({"ok": True, "user_id": user.id}, status=200)


class RegisterAPIView(LdapUserCreationMixin, AnonymousAPIView):
    """Регистрация: создаём учётку в LDAP (disabled) с паролем, в БД — set_unusable_password.
    
    Использует LdapUserCreationMixin для вынесения LDAP-специфичной логики.
    """
    parser_classes = (JSONParser, FormParser, MultiPartParser)

    @extend_schema(
        tags=["Auth"],
        summary="Зарегистрировать нового пользователя",
        request=RegisterSerializer,
        responses={
            201: inline_serializer(
                "RegisterResponse",
                {
                    "id": serializers.IntegerField(),
                    "email": serializers.EmailField(),
                    "email_verified": serializers.BooleanField(),
                    "is_active": serializers.BooleanField(),
                },
            ),
            200: inline_serializer(
                "RegisterPendingVerificationResponse",
                {
                    "ok": serializers.BooleanField(),
                    "pending_verification": serializers.BooleanField(),
                    "user_id": serializers.IntegerField(),
                },
            ),
            400: OpenApiResponse(description="Ошибка валидации или занятый email/телефон."),
        },
    )
    @transaction.atomic
    def post(self, request):
        # Логируем входящие данные для диагностики
        logger.warning(f"[REGISTER] Received data: {request.data}")
        logger.warning(f"[REGISTER] Content-Type: {request.content_type}")

        ser = RegisterSerializer(data=request.data)
        if not ser.is_valid():
            logger.warning(f"[REGISTER] Validation errors: {ser.errors}")
        ser.is_valid(raise_exception=True)
        v = ser.validated_data

        email = v["email"].strip().lower()
        password = v["password"]
        phone_norm = _normalize_phone(
            v.get("phone_number") or request.data.get("phone")
        )
        logger.warning(f"[REGISTER] Phone normalization: input={v.get('phone_number')}, normalized={phone_norm}")
        if not phone_norm:
            logger.error(f"[REGISTER] Phone normalization FAILED for: {v.get('phone_number')}")
            return Response({"ok": False, "error": "invalid_phone"}, status=400)

        existing_phone = Employee.objects.filter(
            phone_number=phone_norm).first()
        if existing_phone:
            logger.warning(
                "[REGISTER] Phone %s already used by user id=%s",
                phone_norm,
                existing_phone.id,
            )
            return Response(
                {
                    "ok": False,
                    "error": "phone_taken",
                    "detail": "Номер телефона уже зарегистрирован."
                    " Войдите в существующий аккаунт или используйте другой номер.",
                    "phone_number": [
                        "Этот номер телефона уже привязан к другому аккаунту."
                    ],
                },
                status=400,
            )

        user = Employee.objects.filter(email__iexact=email).first()
        if user:
            logger.warning(f"[REGISTER] User exists: email={email}, verified={user.email_verified}")
            if user.email_verified:
                # Email уже верифицирован - нельзя регистрироваться
                logger.error(f"[REGISTER] Email already taken and verified: {email}")
                return Response({"ok": False, "error": "email_taken"}, status=400)
            else:
                # Есть неверифицированный пользователь - повторная отправка кода
                return Response(
                    {"ok": True, "pending_verification": True, "user_id": user.id},
                    status=200,
                )

        avatar_file = v.get("avatar") or getattr(
            request, "FILES", {}).get("avatar")
        avatar_bytes = None
        avatar_name = None
        if avatar_file:
            try:
                avatar_bytes = (
                    avatar_file.read() if hasattr(avatar_file, "read") else None
                )
                avatar_name = getattr(
                    avatar_file, "name", None) or "avatar.jpg"
            except Exception:
                avatar_bytes = None
                avatar_name = None

        # Создаём пользователя (миксин сам выберет LDAP или БД режим)
        emp, error_response = self.create_user(
            first_name=v["first_name"],
            last_name=v["last_name"],
            email=email,
            phone=phone_norm,
            password=password,
            avatar_bytes=avatar_bytes,
            is_active=False,  # не активен до верификации email
        )
        if error_response:
            return error_response

        # 2) Заполняем доп.поля БД
        if avatar_bytes:
            try:
                emp.avatar.save(avatar_name, ContentFile(
                    avatar_bytes), save=False)
            except Exception:
                pass

        emp.telegram = v.get("telegram", "")
        emp.whatsapp = v.get("whatsapp", "")
        emp.wechat = v.get("wechat", "")
        emp.birth_date = v["birth_date"]
        emp.gender = v.get("gender")  # опциональное поле

        if v.get("patronymic"):
            emp.patronymic = v["patronymic"]

        pos_id = v.get("position")
        if pos_id and Position.objects.filter(pk=pos_id).exists():
            emp.position_id = pos_id

        emp.save()

        skills_ids = v.get("skills") or []
        if skills_ids:
            emp.skills.set(Skill.objects.filter(pk__in=skills_ids))

        # 3) Отправляем код верификации
        emp.email_activation_code = get_random_string(6, "0123456789")
        emp.save(update_fields=["email_activation_code"])
        send_templated_mail(
            subject="Подтверждение регистрации",
            to=[emp.email],
            template_base="emails/registration_verify_code",
            context={"code": emp.email_activation_code, "user": emp},
        )

        return Response(
            {
                "id": emp.id,
                "email": emp.email,
                "email_verified": emp.email_verified,
                "is_active": emp.is_active,
            },
            status=status.HTTP_201_CREATED,
        )
