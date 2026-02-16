"""Auth-related views: регистрация, подтверждение email, повторная отправка кода."""

from __future__ import annotations

import logging

from common.emails import send_templated_mail
from datetime import timedelta
from django.core.files.base import ContentFile
from django.db import transaction
from django.utils import timezone
from django.utils.crypto import get_random_string
from employees.ldap.directory_service import DirectoryService, DirectoryUserDTO
from employees.ldap.errors import (
    DirectoryDbError,
    DirectoryLdapError,
    DirectoryServiceError,
)
from employees.models import Position, Skill
from employees.utils import _normalize_phone
from rest_framework import status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from ..serializers import EmailSerializer, EmailVerifySerializer, RegisterSerializer
from ._helpers import Employee, _is_ldap_enabled

logger = logging.getLogger(__name__)


class ResendEmailAPIView(APIView):
    """POST /api/v1/auth/resend-email/  body: {"email": "..."}"""

    throttle_scope = "anon"
    permission_classes = [AllowAny]

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


class VerifyEmailAPIView(APIView):
    throttle_scope = "anon"
    permission_classes = [AllowAny]

    def post(self, request):
        """Подтверждает email и активирует пользователя.

        В режиме с LDAP активирует запись в LDAP.
        В режиме без LDAP просто активирует пользователя в БД.
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

        ldap_enabled = _is_ldap_enabled()

        if ldap_enabled:
            # Режим с LDAP: активируем запись в LDAP
            try:
                from employees.models import LdapSyncState

                svc = DirectoryService()

                # Проверяем наличие LDAP-идентификаторов в LdapSyncState
                sync_state = LdapSyncState.objects.filter(
                    model="employee", object_pk=str(user.pk)
                ).first()

                has_ldap = sync_state and (sync_state.ldap_dn or sync_state.ldap_guid)

                if has_ldap:
                    # Запись существует - активируем через DirectoryService
                    user = svc.update_user(user, {"is_active": True})
                else:
                    # LDAP запись не найдена - активируем только в БД
                    logger.warning(
                        f"User {email} has no LDAP sync state, activating in DB only"
                    )
                    user.is_active = True
                    user.save(update_fields=["is_active"])

                # Убеждаемся, что БД тоже активна
                if not user.is_active:
                    user.is_active = True
                    user.save(update_fields=["is_active"])
            except DirectoryLdapError as e:
                # Если LDAP недоступен, всё равно активируем в БД
                logger.warning(
                    f"LDAP error during activation for {email}: {e}, activating in DB"
                )
                user.is_active = True
                user.save(update_fields=["is_active"])
            except DirectoryDbError as e:
                return Response(
                    {"ok": False, "error": "db_error", "detail": str(e)}, status=500
                )
            except DirectoryServiceError as e:
                # При ошибке сервиса тоже активируем в БД
                logger.warning(
                    f"Service error during activation for {email}: {e}, activating in DB"
                )
                user.is_active = True
                user.save(update_fields=["is_active"])
        else:
            # Режим без LDAP: просто активируем пользователя в БД
            if not user.is_active:
                user.is_active = True
                user.save(update_fields=["is_active"])

        return Response({"ok": True, "user_id": user.id}, status=200)


class RegisterAPIView(APIView):
    """Регистрация: создаём учётку в LDAP (disabled) с паролем, в БД — set_unusable_password."""

    throttle_scope = "anon"
    permission_classes = [AllowAny]
    parser_classes = (JSONParser, FormParser, MultiPartParser)

    @transaction.atomic
    def post(self, request):
        # Логируем входящие данные для диагностики
        logger.warning(f"[REGISTER] Received data: {request.data}")
        logger.warning(f"[REGISTER] Content-Type: {request.content_type}")

        # 0) хотя бы один контакт
        if not (
            request.data.get("telegram")
            or request.data.get("whatsapp")
            or request.data.get("wechat")
        ):
            logger.warning("[REGISTER] No contact provided")
            return Response(
                {
                    "detail": "Заполните хотя бы одно из полей: WhatsApp, WeChat или Telegram"
                },
                status=400,
            )

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
        if not phone_norm:
            return Response({"ok": False, "error": "invalid_phone"}, status=400)

        existing_phone = Employee.objects.filter(phone_number=phone_norm).first()
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
            if user.email_verified:
                # Email уже верифицирован - нельзя регистрироваться
                return Response({"ok": False, "error": "email_taken"}, status=400)
            else:
                # Есть неверифицированный пользователь - повторная отправка кода
                return Response(
                    {"ok": True, "pending_verification": True, "user_id": user.id},
                    status=200,
                )

        avatar_file = v.get("avatar") or getattr(request, "FILES", {}).get("avatar")
        avatar_bytes = None
        avatar_name = None
        if avatar_file:
            try:
                avatar_bytes = (
                    avatar_file.read() if hasattr(avatar_file, "read") else None
                )
                avatar_name = getattr(avatar_file, "name", None) or "avatar.jpg"
            except Exception:
                avatar_bytes = None
                avatar_name = None

        ldap_enabled = _is_ldap_enabled()

        if ldap_enabled:
            # Режим с LDAP: создаём disabled учётку в LDAP + пароль
            svc = DirectoryService()
            dto = DirectoryUserDTO(
                first_name=v["first_name"],
                last_name=v["last_name"],
                email=email,
                phone_e164=phone_norm,
                department_dn=None,
                group_cns=[],
                initial_password=password,  # пароль идёт только в LDAP
                avatar_bytes=avatar_bytes,
                is_active=False,  # disabled до верификации
            )
            try:
                emp = svc.create_user(dto)
            except DirectoryLdapError as e:
                return Response(
                    {"ok": False, "error": "ldap_error", "detail": str(e)}, status=502
                )
            except DirectoryDbError as e:
                return Response(
                    {"ok": False, "error": "db_error", "detail": str(e)}, status=500
                )
        else:
            # Режим без LDAP: создаём пользователя напрямую в БД
            emp = Employee.objects.create(
                first_name=v["first_name"],
                last_name=v["last_name"],
                email=email,
                phone_number=phone_norm,
                is_active=False,  # не активен до верификации email
                is_ldap_managed=False,
            )
            # Устанавливаем пароль в БД
            emp.set_password(password)

        # 2) Заполняем доп.поля БД
        if avatar_bytes:
            try:
                emp.avatar.save(avatar_name, ContentFile(avatar_bytes), save=False)
            except Exception:
                pass

        emp.telegram = v.get("telegram", "")
        emp.whatsapp = v.get("whatsapp", "")
        emp.wechat = v.get("wechat", "")
        emp.birth_date = v["birth_date"]
        emp.gender = v["gender"]  # обязательное поле

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
