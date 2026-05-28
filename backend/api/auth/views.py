from __future__ import annotations

import logging
from datetime import timedelta

from django.conf import settings
from api.v1.employees.serializers import (
    EmailSerializer,
    EmailVerifySerializer,
    RegisterSerializer,
)
from api.v1.employees.views._helpers import Employee
from api.v1.employees.views.mixins import LdapPasswordMixin, LdapUserCreationMixin
from common.emails import send_templated_mail
from django.contrib.auth import authenticate
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.files.base import ContentFile
from django.db import transaction
from django.utils import timezone
from django.utils.crypto import get_random_string
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from drf_spectacular.utils import (
    OpenApiExample,
    OpenApiParameter,
    OpenApiResponse,
    extend_schema,
    inline_serializer,
)
from employees.models import Position, Skill
from employees.utils import _normalize_phone
from rest_framework import serializers, status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import InvalidToken
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from .models import UserAuthSession
from .serializers import (
    ChangePasswordRequestSerializer,
    ChangePasswordResponseSerializer,
    PhoneOrEmailTokenObtainPairSerializer,
    PasswordResetConfirmRequestSerializer,
    PasswordResetConfirmResponseSerializer,
    PasswordResetRequestResponseSerializer,
    PasswordResetRequestSerializer,
    QrLoginCreateResponseSerializer,
    QrLoginExchangeRequestSerializer,
    QrLoginRequestActionResponseSerializer,
    QrLoginRequestCreateResponseSerializer,
    QrLoginRequestDetailResponseSerializer,
    QrLoginRequestStatusRequestSerializer,
    QrLoginRequestStatusResponseSerializer,
    SessionBulkActionResponseSerializer,
    SessionSerializer,
    SessionTokenRefreshSerializer,
    TokenPairResponseSerializer,
    TokenRefreshRequestSerializer,
    TokenRefreshResponseSerializer,
)
from .services import (
    SESSION_ID_CLAIM,
    approve_qr_login_request,
    cancel_qr_login_request,
    create_qr_login_request,
    create_qr_login_token,
    deny_qr_login_request,
    exchange_qr_login_token,
    get_qr_login_request_for_approval,
    poll_qr_login_request,
)

logger = logging.getLogger(__name__)


def _resolve_employee_by_login(login: str) -> Employee | None:
    normalized_login = (login or "").strip()
    if not normalized_login:
        return None

    if "@" in normalized_login:
        return Employee.objects.filter(email__iexact=normalized_login).first()

    normalized_phone = _normalize_phone(normalized_login)
    if not normalized_phone:
        return None
    return Employee.objects.filter(phone_number=normalized_phone).first()


def _build_frontend_password_reset_link(*, uid: str, token: str) -> str:
    site_url = getattr(settings, "SITE_URL", "https://corp.robotail.pro").rstrip("/")
    return f"{site_url}/reset-password?uid={uid}&token={token}"


class AnonymousAPIView(APIView):
    authentication_classes = []
    throttle_scope = "anon"
    permission_classes = [AllowAny]


@extend_schema(
    tags=["Auth"],
    summary="Получить JWT access и refresh токены",
    description=(
        "Принимает email или телефон вместе с паролем. "
        "Если передан телефон, backend найдёт пользователя "
        "и использует его email "
        "для стандартной JWT-аутентификации."
    ),
    request=PhoneOrEmailTokenObtainPairSerializer,
    responses={
        200: TokenPairResponseSerializer,
        401: OpenApiResponse(
            description=(
                "Неверные учетные данные или email пользователя "
                "не подтвержден."
            ),
        ),
    },
    examples=[
        OpenApiExample(
            "Вход по email",
            value={"email": "user@example.com", "password": "Str0ngPass!"},
            request_only=True,
        ),
        OpenApiExample(
            "Вход по телефону",
            value={"phone_number": "+79990000001", "password": "Str0ngPass!"},
            request_only=True,
        ),
    ],
)
class PhoneOrEmailTokenObtainPairView(TokenObtainPairView):
    serializer_class = PhoneOrEmailTokenObtainPairSerializer


@extend_schema(
    tags=["Auth"],
    summary="Обновить JWT access token",
    description="Принимает refresh token и возвращает новый access token.",
    request=TokenRefreshRequestSerializer,
    responses={
        200: TokenRefreshResponseSerializer,
        401: OpenApiResponse(
            description="Refresh token недействителен, истек или сессия отозвана."
        ),
    },
)
class JWTTokenRefreshView(TokenRefreshView):
    serializer_class = SessionTokenRefreshSerializer


class QrLoginExchangeAPIView(AnonymousAPIView):
    @extend_schema(
        tags=["Auth"],
        summary="Обменять одноразовый QR-токен на JWT access и refresh",
        request=QrLoginExchangeRequestSerializer,
        responses={
            200: TokenPairResponseSerializer,
            401: OpenApiResponse(
                description="QR-токен недействителен, истек или уже использован."
            ),
        },
    )
    def post(self, request):
        serializer = QrLoginExchangeRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            refresh, access = exchange_qr_login_token(
                raw_token=serializer.validated_data["token"],
                request=request,
            )
        except InvalidToken:
            return Response(
                {"detail": "qr_login_token_invalid"},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        return Response(
            {"refresh": refresh, "access": access},
            status=status.HTTP_200_OK,
        )


def _serialize_qr_login_request(qr_request) -> dict:
    return {
        "status": qr_request.status,
        "device_name": qr_request.requester_device_name,
        "ip_address": qr_request.requester_ip_address,
        "created_at": qr_request.created_at,
        "expires_at": qr_request.expires_at,
    }


def _get_current_session_id_from_request(request) -> str | None:
    token = getattr(request, "auth", None)
    if token is None:
        return None
    return token.get(SESSION_ID_CLAIM)


class QrLoginRequestCreateAPIView(AnonymousAPIView):
    @extend_schema(
        tags=["Auth"],
        summary="Создать QR-запрос входа для подтверждения на другом устройстве",
        responses={200: QrLoginRequestCreateResponseSerializer},
    )
    def post(self, request):
        scan_token, client_secret, qr_request = create_qr_login_request(
            request=request,
        )
        return Response(
            {
                "scan_token": scan_token,
                "client_secret": client_secret,
                "expires_at": qr_request.expires_at,
                "device_name": qr_request.requester_device_name,
                "ip_address": qr_request.requester_ip_address,
            },
            status=status.HTTP_200_OK,
        )


class QrLoginRequestStatusAPIView(AnonymousAPIView):
    @extend_schema(
        tags=["Auth"],
        summary="Проверить статус QR-запроса входа",
        request=QrLoginRequestStatusRequestSerializer,
        responses={200: QrLoginRequestStatusResponseSerializer},
    )
    def post(self, request):
        serializer = QrLoginRequestStatusRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            payload = poll_qr_login_request(
                raw_client_secret=serializer.validated_data["client_secret"],
                request=request,
            )
        except InvalidToken:
            return Response(
                {"detail": "qr_login_request_invalid"},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        return Response(payload, status=status.HTTP_200_OK)


class QrLoginRequestCancelAPIView(AnonymousAPIView):
    @extend_schema(
        tags=["Auth"],
        summary="Отменить QR-запрос входа с устройства, которое показывает QR",
        request=QrLoginRequestStatusRequestSerializer,
        responses={200: QrLoginRequestActionResponseSerializer},
    )
    def post(self, request):
        serializer = QrLoginRequestStatusRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            qr_request = cancel_qr_login_request(
                raw_client_secret=serializer.validated_data["client_secret"],
            )
        except InvalidToken:
            return Response(
                {"detail": "qr_login_request_invalid"},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        return Response({"status": qr_request.status}, status=status.HTTP_200_OK)


class QrLoginRequestDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Auth"],
        summary="Получить параметры QR-запроса входа",
        responses={200: QrLoginRequestDetailResponseSerializer},
    )
    def get(self, request, scan_token):
        try:
            qr_request = get_qr_login_request_for_approval(scan_token)
        except InvalidToken:
            return Response(
                {"detail": "qr_login_request_invalid"},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(
            _serialize_qr_login_request(qr_request),
            status=status.HTTP_200_OK,
        )


class QrLoginRequestApproveAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Auth"],
        summary="Подтвердить QR-запрос входа",
        responses={200: QrLoginRequestActionResponseSerializer},
    )
    def post(self, request, scan_token):
        try:
            qr_request = approve_qr_login_request(
                raw_scan_token=scan_token,
                user=request.user,
                current_session_id=_get_current_session_id_from_request(request),
            )
        except InvalidToken:
            return Response(
                {"detail": "qr_login_request_invalid"},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        return Response({"status": qr_request.status}, status=status.HTTP_200_OK)


class QrLoginRequestDenyAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Auth"],
        summary="Отклонить QR-запрос входа",
        responses={200: QrLoginRequestActionResponseSerializer},
    )
    def post(self, request, scan_token):
        try:
            qr_request = deny_qr_login_request(
                raw_scan_token=scan_token,
                user=request.user,
            )
        except InvalidToken:
            return Response(
                {"detail": "qr_login_request_invalid"},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        return Response({"status": qr_request.status}, status=status.HTTP_200_OK)


class ResendEmailAPIView(AnonymousAPIView):
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

        user.is_active = True
        user._ldap_changes = {"is_active": True}
        user.save()

        return Response({"ok": True, "user_id": user.id}, status=200)


class RegisterAPIView(LdapUserCreationMixin, AnonymousAPIView):
    parser_classes = (JSONParser, FormParser, MultiPartParser)

    def is_ldap_enabled(self) -> bool:
        # Сохраняем старую точку patch'а тестов:
        # api.v1.employees.views._is_ldap_enabled
        from api.v1.employees import views as employee_views

        return employee_views._is_ldap_enabled()

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
            400: OpenApiResponse(
                description="Ошибка валидации или занятый email/телефон."
            ),
        },
    )
    @transaction.atomic
    def post(self, request):
        logger.warning("[REGISTER] Received data: %s", request.data)
        logger.warning("[REGISTER] Content-Type: %s", request.content_type)

        ser = RegisterSerializer(data=request.data)
        if not ser.is_valid():
            logger.warning("[REGISTER] Validation errors: %s", ser.errors)
        ser.is_valid(raise_exception=True)
        v = ser.validated_data

        email = v["email"].strip().lower()
        password = v["password"]
        phone_norm = _normalize_phone(
            v.get("phone_number") or request.data.get("phone")
        )
        logger.warning(
            "[REGISTER] Phone normalization: input=%s, normalized=%s",
            v.get("phone_number"),
            phone_norm,
        )
        if not phone_norm:
            logger.error(
                "[REGISTER] Phone normalization FAILED for: %s",
                v.get("phone_number"),
            )
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
                    "detail": (
                        "Номер телефона уже зарегистрирован. "
                        "Войдите в существующий аккаунт "
                        "или используйте другой номер."
                    ),
                    "phone_number": [
                        "Этот номер телефона уже привязан к другому аккаунту."
                    ],
                },
                status=400,
            )

        user = Employee.objects.filter(email__iexact=email).first()
        if user:
            logger.warning(
                "[REGISTER] User exists: email=%s, verified=%s",
                email,
                user.email_verified,
            )
            if user.email_verified:
                logger.error("[REGISTER] Email already taken and verified: %s", email)
                return Response({"ok": False, "error": "email_taken"}, status=400)
            return Response(
                {
                    "ok": True,
                    "pending_verification": True,
                    "user_id": user.id,
                },
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

        emp, error_response = self.create_user(
            first_name=v["first_name"],
            last_name=v["last_name"],
            email=email,
            phone=phone_norm,
            password=password,
            avatar_bytes=avatar_bytes,
            is_active=False,
        )
        if error_response:
            return error_response

        if avatar_bytes:
            try:
                emp.avatar.save(avatar_name, ContentFile(avatar_bytes), save=False)
            except Exception:
                pass

        emp.telegram = v.get("telegram", "")
        emp.whatsapp = v.get("whatsapp", "")
        emp.wechat = v.get("wechat", "")
        emp.birth_date = v["birth_date"]
        emp.gender = v.get("gender")

        if v.get("patronymic"):
            emp.patronymic = v["patronymic"]

        pos_id = v.get("position")
        if pos_id and Position.objects.filter(pk=pos_id).exists():
            emp.position_id = pos_id

        emp.save()

        skills_ids = v.get("skills") or []
        if skills_ids:
            emp.skills.set(Skill.objects.filter(pk__in=skills_ids))

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


class SessionBaseAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get_current_session_id(self, request) -> str | None:
        token = getattr(request, "auth", None)
        if token is None:
            return None
        return token.get(SESSION_ID_CLAIM)


class QrLoginCreateAPIView(SessionBaseAPIView):
    @extend_schema(
        tags=["Auth"],
        summary="Создать одноразовый QR-токен для входа",
        responses={200: QrLoginCreateResponseSerializer},
    )
    def post(self, request):
        raw_token, token = create_qr_login_token(
            user=request.user,
            request=request,
            current_session_id=self.get_current_session_id(request),
        )
        return Response(
            {"token": raw_token, "expires_at": token.expires_at},
            status=status.HTTP_200_OK,
        )


class ChangePasswordAPIView(LdapPasswordMixin, SessionBaseAPIView):
    @extend_schema(
        tags=["Auth"],
        summary="Сменить пароль текущего пользователя",
        request=ChangePasswordRequestSerializer,
        responses={
            200: ChangePasswordResponseSerializer,
            400: OpenApiResponse(
                description="Текущий пароль неверен или новый пароль невалиден."
            ),
            502: OpenApiResponse(
                description="Не удалось обновить пароль в LDAP."
            ),
        },
    )
    def post(self, request):
        serializer = ChangePasswordRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        current_password = serializer.validated_data["current_password"]
        new_password = serializer.validated_data["new_password"]
        user = request.user

        verified_user = authenticate(
            request=request,
            email=user.email,
            password=current_password,
        )
        if verified_user is None or verified_user.pk != user.pk:
            return Response(
                {
                    "current_password": [
                        "Текущий пароль указан неверно."
                    ]
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            updated, error_response = self.update_ldap_password(user, new_password)
        except DjangoValidationError as exc:
            return Response(
                {"new_password": exc.messages},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not updated:
            return error_response

        return Response({"ok": True}, status=status.HTTP_200_OK)


class PasswordResetAPIView(AnonymousAPIView):
    @extend_schema(
        tags=["Auth"],
        summary="Запросить письмо для сброса пароля",
        request=PasswordResetRequestSerializer,
        responses={200: PasswordResetRequestResponseSerializer},
    )
    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = _resolve_employee_by_login(serializer.validated_data["login"])
        if user and user.email:
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            token = default_token_generator.make_token(user)
            reset_link = _build_frontend_password_reset_link(uid=uid, token=token)

            send_templated_mail(
                subject="Восстановление пароля",
                to=[user.email],
                template_base="emails/password_reset_link",
                context={
                    "user": user,
                    "reset_link": reset_link,
                    "site_url": getattr(settings, "SITE_URL", "https://corp.robotail.pro"),
                },
            )

        # Намеренно не раскрываем, существует ли пользователь.
        return Response({"ok": True}, status=status.HTTP_200_OK)


class PasswordResetConfirmAPIView(LdapPasswordMixin, AnonymousAPIView):
    @extend_schema(
        tags=["Auth"],
        summary="Подтвердить сброс пароля по uid и token",
        request=PasswordResetConfirmRequestSerializer,
        responses={
            200: PasswordResetConfirmResponseSerializer,
            400: OpenApiResponse(description="Ссылка недействительна или пароль невалиден."),
            502: OpenApiResponse(description="Не удалось обновить пароль в LDAP."),
        },
    )
    def post(self, request):
        serializer = PasswordResetConfirmRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            user_id = force_str(
                urlsafe_base64_decode(serializer.validated_data["uid"])
            )
        except (TypeError, ValueError, OverflowError):
            return Response(
                {"token": ["Ссылка для восстановления недействительна."]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = Employee.objects.filter(pk=user_id).first()
        if user is None or not default_token_generator.check_token(
            user, serializer.validated_data["token"]
        ):
            return Response(
                {"token": ["Ссылка для восстановления недействительна или устарела."]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            updated, error_response = self.update_ldap_password(
                user,
                serializer.validated_data["new_password"],
            )
        except DjangoValidationError as exc:
            return Response(
                {"new_password": exc.messages},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not updated:
            return error_response

        return Response({"ok": True}, status=status.HTTP_200_OK)


class SessionListAPIView(SessionBaseAPIView):
    @extend_schema(
        tags=["Auth"],
        summary="Список активных сессий пользователя",
        responses={200: SessionSerializer(many=True)},
    )
    def get(self, request):
        current_session_id = self.get_current_session_id(request)
        queryset = UserAuthSession.objects.filter(
            user=request.user,
            revoked_at__isnull=True,
        ).order_by("-last_seen_at", "-created_at")
        serializer = SessionSerializer(
            queryset,
            many=True,
            context={"current_session_id": current_session_id},
        )
        return Response(serializer.data)


class SessionDetailAPIView(SessionBaseAPIView):
    @extend_schema(
        tags=["Auth"],
        summary="Завершить одну сессию",
        parameters=[
            OpenApiParameter(
                name="session_id",
                type=str,
                location=OpenApiParameter.PATH,
            )
        ],
        responses={204: OpenApiResponse(description="Сессия завершена.")},
    )
    def delete(self, request, session_id):
        session = UserAuthSession.objects.filter(
            user=request.user,
            session_id=session_id,
            revoked_at__isnull=True,
        ).first()
        if not session:
            return Response(status=status.HTTP_404_NOT_FOUND)

        reason = "self_logout" if str(session.session_id) == str(
            self.get_current_session_id(request)
        ) else "manual_logout"
        session.revoke(reason=reason)
        return Response(status=status.HTTP_204_NO_CONTENT)


class LogoutOtherSessionsAPIView(SessionBaseAPIView):
    @extend_schema(
        tags=["Auth"],
        summary="Завершить все остальные сессии",
        responses={200: SessionBulkActionResponseSerializer},
    )
    def post(self, request):
        current_session_id = self.get_current_session_id(request)
        sessions = UserAuthSession.objects.filter(
            user=request.user,
            revoked_at__isnull=True,
        ).exclude(session_id=current_session_id)

        revoked = 0
        for session in sessions:
            session.revoke(reason="logout_others")
            revoked += 1

        return Response({"revoked": revoked}, status=status.HTTP_200_OK)
