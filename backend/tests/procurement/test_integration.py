"""
Тесты интеграции модуля закупок.
Сигналы, уведомления, WebSocket события.
"""

import pytest
from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model

from notifications.models import (
    Notification,
    NotificationCategory,
    NotificationType,
)
from procurement.constants import ApprovalRole, ApprovalStatus, ProcurementStatus
from procurement.models import (
    Approval,
    Budget,
    ProcurementItem,
    ProcurementRequest,
)
from procurement.signals import broadcast_request_update

Employee = get_user_model()


@pytest.fixture
def notification_setup(db):
    """Настройка типов уведомлений для тестов."""
    category, _ = NotificationCategory.objects.get_or_create(
        code='procurement',
        defaults={
            'name': 'Закупки',
            'description': 'Уведомления закупок',
            'icon': 'bi-cart3',
            'color': '#17a2b8',
            'order': 60,
        }
    )

    notification_types = [
        'procurement_new_request',
        'procurement_pending_approval',
        'procurement_approved',
        'procurement_rejected',
        'procurement_completed',
        'procurement_stage_approved',
    ]

    for type_code in notification_types:
        NotificationType.objects.get_or_create(
            code=type_code,
            defaults={
                'category': category,
                'name': type_code.replace('_', ' ').title(),
                'description': f'Уведомление {type_code}',
                'priority': 'normal',
                'default_channels': {
                    'web': True,
                    'email': False,
                    'telegram': False
                },
            }
        )

    return category


@pytest.fixture
def department_with_head(department_factory, user_factory, link_factory):
    """Отдел с руководителем."""
    dept = department_factory(name="IT отдел")
    head = user_factory(
        email="head@test.com",
        first_name="Руководитель",
        last_name="Отдела",
    )
    head.is_staff = True
    head.save()
    dept.head = head
    dept.save()
    link_factory(head, dept, is_active=True)
    return dept


@pytest.fixture
def requestor(user_factory, department_with_head, link_factory):
    """Пользователь-заявитель."""
    user = user_factory(
        email="requestor@test.com",
        first_name="Заявитель",
        last_name="Тестовый",
    )
    link_factory(user, department_with_head, is_active=True)
    return user


@pytest.fixture
def budget_for_department(department_with_head):
    """Бюджет для отдела."""
    from django.utils import timezone
    now = timezone.now()
    return Budget.objects.create(
        department=department_with_head,
        year=now.year,
        quarter=(now.month - 1) // 3 + 1,
        allocated_amount=Decimal('100000.00'),
    )


@pytest.mark.django_db
class TestProcurementSignals:
    """Тесты сигналов модуля закупок."""

    def test_new_request_notifies_department_head(
        self, notification_setup, department_with_head, requestor
    ):
        """Создание заявки уведомляет руководителя отдела."""
        # Очищаем уведомления
        Notification.objects.all().delete()

        request = ProcurementRequest.objects.create(
            title="Тестовая заявка",
            description="Описание",
            department=department_with_head,
            requestor=requestor,
        )

        # Проверяем уведомление руководителю
        notifications = Notification.objects.filter(
            recipient=department_with_head.head
        )
        assert notifications.exists()
        assert 'Новая заявка' in notifications.first().title

    def test_status_change_triggers_notification(
        self, notification_setup, department_with_head, requestor,
        budget_for_department
    ):
        """Изменение статуса создаёт уведомление."""
        Notification.objects.all().delete()

        request = ProcurementRequest.objects.create(
            title="Заявка на согласование",
            department=department_with_head,
            requestor=requestor,
        )

        # Добавляем позицию
        ProcurementItem.objects.create(
            request=request,
            name="Тестовый товар",
            quantity=1,
            estimated_unit_price=Decimal('5000.00'),
        )

        # Создаём согласование
        Approval.objects.create(
            request=request,
            approver=department_with_head.head,
            role=ApprovalRole.DEPARTMENT_HEAD,
        )

        # Отправляем на согласование
        request.status = ProcurementStatus.PENDING
        request.save()

        # Проверяем уведомление согласующему
        pending_notifications = Notification.objects.filter(
            notification_type__code='procurement_pending_approval'
        )
        assert pending_notifications.exists()


@pytest.mark.django_db
class TestBroadcastFunction:
    """Тесты функции broadcast."""

    @patch('procurement.signals.get_channel_layer')
    def test_broadcast_sends_to_department_group(
        self, mock_get_channel_layer,
        notification_setup, department_with_head, requestor
    ):
        """broadcast_request_update отправляет в группу отдела."""
        mock_channel_layer = MagicMock()
        mock_get_channel_layer.return_value = mock_channel_layer

        request = ProcurementRequest(
            id=1,
            title="Тест",
            status=ProcurementStatus.DRAFT,
            department=department_with_head,
            requestor=requestor,
        )

        broadcast_request_update(request, 'test_event')

        # Проверяем вызов group_send
        assert mock_channel_layer.group_send.call_count >= 1

    @patch('procurement.signals.get_channel_layer')
    def test_broadcast_handles_missing_channel_layer(
        self, mock_get_channel_layer,
        notification_setup, department_with_head, requestor
    ):
        """broadcast_request_update обрабатывает отсутствие channel_layer."""
        mock_get_channel_layer.return_value = None

        request = ProcurementRequest(
            id=1,
            title="Тест",
            status=ProcurementStatus.DRAFT,
            department=department_with_head,
            requestor=requestor,
        )

        # Не должно вызвать исключение
        broadcast_request_update(request, 'test_event')


@pytest.mark.django_db
class TestApprovalNotifications:
    """Тесты уведомлений при согласовании."""

    def test_approval_approved_notifies_requestor(
        self, notification_setup, department_with_head, requestor,
        budget_for_department
    ):
        """Одобрение согласования уведомляет заявителя."""
        Notification.objects.all().delete()

        request = ProcurementRequest.objects.create(
            title="Заявка",
            department=department_with_head,
            requestor=requestor,
            status=ProcurementStatus.PENDING,
        )

        approval = Approval.objects.create(
            request=request,
            approver=department_with_head.head,
            role=ApprovalRole.DEPARTMENT_HEAD,
            status=ApprovalStatus.PENDING,
        )

        # Одобряем
        approval.status = ApprovalStatus.APPROVED
        approval.save()

        # Проверяем уведомление заявителю
        stage_notifications = Notification.objects.filter(
            recipient=requestor,
            notification_type__code='procurement_stage_approved'
        )
        assert stage_notifications.exists()

    def test_approval_rejected_notifies_requestor(
        self, notification_setup, department_with_head, requestor,
        budget_for_department
    ):
        """Отклонение согласования уведомляет заявителя."""
        Notification.objects.all().delete()

        request = ProcurementRequest.objects.create(
            title="Заявка",
            department=department_with_head,
            requestor=requestor,
            status=ProcurementStatus.PENDING,
        )

        approval = Approval.objects.create(
            request=request,
            approver=department_with_head.head,
            role=ApprovalRole.DEPARTMENT_HEAD,
            status=ApprovalStatus.PENDING,
        )

        # Отклоняем
        approval.status = ApprovalStatus.REJECTED
        approval.comment = "Недостаточно обоснования"
        approval.save()

        # Проверяем уведомление заявителю
        reject_notifications = Notification.objects.filter(
            recipient=requestor,
            notification_type__code='procurement_rejected'
        )
        assert reject_notifications.exists()
