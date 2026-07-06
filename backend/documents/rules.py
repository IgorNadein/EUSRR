# documents/rules.py
"""
django-rules: декларативные правила доступа для Document

Адаптация правил доступа для моделей с django-filer.
https://github.com/dfunckt/django-rules
"""

import rules


# -----------------------------------------------------------------------------
# ПРЕДИКАТЫ (predicates)
# -----------------------------------------------------------------------------


@rules.predicate
def is_superuser(user):
    """Суперпользователь имеет все права"""
    return user.is_superuser


@rules.predicate
def is_document_uploader(user, document):
    """Пользователь загрузил документ"""
    if document is None:
        return False
    return document.uploaded_by == user


@rules.predicate
def has_document_access(user, document):
    """
    Пользователь имеет доступ к документу через:
    - sent_to_all=True (все активные сотрудники)
    - departments (пользователь в одном из отделов-получателей)
    - recipients (пользователь в списке получателей)
    """
    if document is None:
        return False

    # Документ для всех
    if document.sent_to_all and user.is_active:
        return True

    if document.uploaded_by_id == getattr(user, "pk", None):
        return True

    # Проверка через активные связи с отделами
    if document.departments.filter(
        employeedepartment__employee=user,
        employeedepartment__is_active=True,
    ).exists():
        return True

    # Прямой доступ через recipients
    if document.recipients.filter(id=user.id).exists():
        return True

    return False


@rules.predicate
def can_manage_documents(user):
    """
    Пользователь может управлять документами.
    Адаптируйте под вашу логику (по должности, группе и т.д.)
    """
    if not hasattr(user, "position"):
        return False

    position_name = getattr(user.position, "name", "").lower()
    return any(
        keyword in position_name
        for keyword in [
            "руководитель",
            "начальник",
            "директор",
            "заведующий",
            "кадры",
        ]
    )


@rules.predicate
def is_same_department(user, document):
    """Документ относится к отделу пользователя"""
    if document is None or not hasattr(user, "department"):
        return False

    return document.departments.filter(id=user.department.id).exists()


@rules.predicate
def has_acknowledged_document(user, document):
    """Пользователь уже ознакомился с документом"""
    if document is None:
        return False

    from documents.models import DocumentAcknowledgement

    return DocumentAcknowledgement.objects.filter(
        document=document, user=user
    ).exists()


# -----------------------------------------------------------------------------
# ПРАВИЛА (rules)
# -----------------------------------------------------------------------------

# Просмотр документа
rules.add_rule(
    "documents.view_document",
    is_superuser | is_document_uploader | has_document_access,
)

# Изменение документа (только загрузивший и менеджеры)
rules.add_rule(
    "documents.change_document",
    is_superuser | is_document_uploader | can_manage_documents,
)

# Удаление документа (только загрузивший, менеджеры и superuser)
rules.add_rule(
    "documents.delete_document",
    is_superuser | is_document_uploader | can_manage_documents,
)

# Скачивание документа (все, кто имеет доступ на просмотр)
rules.add_rule(
    "documents.download_document",
    is_superuser | is_document_uploader | has_document_access,
)

# Отметка об ознакомлении (только те, у кого есть доступ)
rules.add_rule("documents.acknowledge_document", has_document_access)

# Просмотр списка ознакомившихся (все, у кого есть доступ к документу)
rules.add_rule(
    "documents.view_acknowledgements_document",
    is_superuser | is_document_uploader | has_document_access,
)

# Выдача доступа другим пользователям (только загрузивший и менеджеры)
rules.add_rule(
    "documents.share_document",
    is_superuser | is_document_uploader | can_manage_documents,
)

# Просмотр истории версий документа (filer + reversion)
rules.add_rule(
    "documents.view_document_history",
    is_superuser | is_document_uploader | can_manage_documents,
)

# Просмотр всех документов отдела
rules.add_rule(
    "documents.view_department_documents", is_superuser | can_manage_documents
)


# -----------------------------------------------------------------------------
# PERMISSIONS ДЛЯ МОДЕЛЕЙ
# -----------------------------------------------------------------------------

# Если вы хотите переопределить стандартные Django permissions:
rules.add_perm("documents.view_document", is_superuser | has_document_access)
rules.add_perm(
    "documents.change_document",
    is_superuser | is_document_uploader | can_manage_documents,
)
rules.add_perm(
    "documents.delete_document",
    is_superuser | is_document_uploader | can_manage_documents,
)
# Создавать документы могут только superuser и те, у кого есть модельные права
# (проверяется через DjangoModelPermissions в permission_classes ViewSet)
# rules.add_perm('documents.add_document', is_superuser | can_manage_documents)
# Комментируем, чтобы add_document проверялся через DjangoModelPermissions


# Примеры использования перенесены в проектную документацию.
