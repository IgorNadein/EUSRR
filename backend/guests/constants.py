from django.db import models


GUEST_ID_MIN = 900_000_000_000_000
GUEST_ID_START = 900_000_000_000_001
GUEST_ID_MAX = 999_999_999_999_999


class GuestVisitStatus(models.TextChoices):
    DRAFT = "draft", "Черновик"
    PENDING = "pending", "На рассмотрении"
    NEEDS_INFO = "needs_info", "Требуется информация"
    APPROVED = "approved", "Одобрено"
    REJECTED = "rejected", "Отклонено"
    CANCELLED = "cancelled", "Отменено"
    EXPIRED = "expired", "Истекло"
    REVOKED = "revoked", "Отозвано"


class GuestVisitEventType(models.TextChoices):
    CREATED = "created", "Создано"
    SUBMITTED = "submitted", "Отправлено"
    NEEDS_INFO_REQUESTED = "needs_info_requested", "Запрошена информация"
    INFO_PROVIDED = "info_provided", "Информация предоставлена"
    APPROVED = "approved", "Одобрено"
    REJECTED = "rejected", "Отклонено"
    DECISION_CHANGED = "decision_changed", "Решение изменено"
    CANCELLED = "cancelled", "Отменено"
    REVOKED = "revoked", "Отозвано"
    EXPIRED = "expired", "Истекло"
    LDAP_CREATED = "ldap_created", "LDAP создан"
    LDAP_UPDATED = "ldap_updated", "LDAP обновлен"
    LDAP_ENABLED = "ldap_enabled", "LDAP перемещен в Active OU"
    LDAP_DISABLED = "ldap_disabled", "LDAP перемещен в Deactivated OU"
    LDAP_FAILED = "ldap_failed", "Ошибка LDAP"
    LDAP_SKIPPED = "ldap_skipped", "LDAP пропущен"
    DOCUMENT_ATTACHED = "document_attached", "Документ прикреплен"
    DOCUMENT_REMOVED = "document_removed", "Документ удален"
    INVITER_INACTIVE_DETECTED = (
        "inviter_inactive_detected",
        "Приглашающий неактивен",
    )


ACTIVE_VISIT_STATUSES = {
    GuestVisitStatus.APPROVED,
}


EDITABLE_BY_AUTHOR_STATUSES = {
    GuestVisitStatus.DRAFT,
    GuestVisitStatus.NEEDS_INFO,
}
