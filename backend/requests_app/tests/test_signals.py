"""
Тесты для автоматического создания EmployeeAction из заявок (signals).
"""
import pytest
from datetime import date, timedelta
from unittest.mock import patch
from django.utils import timezone

from requests_app.models import Request
from requests_app.enums import RequestStatus
from employees.models import EmployeeAction
from employees.signals import IMMEDIATE_ACTION_MAPPING, SCHEDULED_ACTION_MAPPING


@pytest.mark.django_db
class TestRequestSignals:
    """Тесты сигналов создания EmployeeAction из Request."""

    def test_immediate_action_dismissal(self, user_factory):
        """Увольнение создаёт EmployeeAction немедленно при одобрении."""
        employee = user_factory()
        approver = user_factory()

        # Создаём заявку на увольнение
        request = Request.objects.create(
            employee=employee,
            type='dismissal',
            status=RequestStatus.PENDING,
            date_from=date.today(),
            comment='Увольнение по собственному желанию'
        )

        # Проверяем что события ещё нет
        assert not EmployeeAction.objects.filter(
            extra__request_id=request.id
        ).exists()

        # Одобряем заявку
        request.status = RequestStatus.APPROVED
        request.approver = approver
        request.decided_at = timezone.now()
        request.save()

        # Проверяем что событие создалось
        action = EmployeeAction.objects.get(
            employee=employee,
            action='dismissed',
            extra__request_id=request.id
        )

        assert action.action == 'dismissed'
        assert action.extra['request_id'] == request.id
        assert action.extra['approved_by'] == approver.id
        assert action.extra['immediate'] is True
        assert 'Заявление #' in action.comment

    def test_immediate_action_transfer(self, user_factory):
        """Перевод создаёт EmployeeAction немедленно при одобрении."""
        employee = user_factory()
        approver = user_factory()

        request = Request.objects.create(
            employee=employee,
            type='transfer',
            status=RequestStatus.PENDING,
            date_from=date.today(),
        )

        # Одобряем
        request.status = RequestStatus.APPROVED
        request.approver = approver
        request.save()

        # Проверяем событие
        action = EmployeeAction.objects.get(
            employee=employee,
            action='transferred',
            extra__request_id=request.id
        )

        assert action.action == 'transferred'
        assert action.extra['immediate'] is True

    @patch('employees.signals._schedule_delayed_action')
    def test_scheduled_action_vacation(self, mock_schedule, user_factory):
        """Отпуск запускает планирование через Celery."""
        employee = user_factory()
        approver = user_factory()
        future_date = date.today() + timedelta(days=7)

        request = Request.objects.create(
            employee=employee,
            type='vacation',
            status=RequestStatus.PENDING,
            date_from=future_date,
            date_to=future_date + timedelta(days=10),
        )

        # Одобряем
        request.status = RequestStatus.APPROVED
        request.approver = approver
        request.save()

        # Проверяем что вызвалась функция планирования
        mock_schedule.assert_called_once()
        called_request = mock_schedule.call_args[0][0]
        assert called_request.id == request.id

    @patch('employees.signals._schedule_delayed_action')
    def test_scheduled_action_sick_leave(self, mock_schedule, user_factory):
        """Больничный запускает планирование через Celery."""
        employee = user_factory()
        approver = user_factory()
        future_date = date.today() + timedelta(days=3)

        request = Request.objects.create(
            employee=employee,
            type='sick_leave',
            status=RequestStatus.PENDING,
            date_from=future_date,
        )

        request.status = RequestStatus.APPROVED
        request.approver = approver
        request.save()

        mock_schedule.assert_called_once()

    def test_no_duplicate_actions(self, user_factory):
        """Повторное сохранение одобренной заявки не создаёт дубликаты."""
        employee = user_factory()
        approver = user_factory()

        request = Request.objects.create(
            employee=employee,
            type='dismissal',
            status=RequestStatus.PENDING,
            date_from=date.today(),
        )

        # Одобряем
        request.status = RequestStatus.APPROVED
        request.approver = approver
        request.save()

        # Первое событие создалось
        assert EmployeeAction.objects.filter(
            employee=employee,
            action='dismissed',
            extra__request_id=request.id
        ).count() == 1

        # Меняем комментарий и сохраняем снова
        request.comment = 'Обновлённый комментарий'
        request.save()

        # Дубликат не создался
        assert EmployeeAction.objects.filter(
            employee=employee,
            action='dismissed',
            extra__request_id=request.id
        ).count() == 1

    def test_signal_not_fired_on_creation(self, user_factory):
        """Сигнал не срабатывает при создании (только при одобрении)."""
        employee = user_factory()

        request = Request.objects.create(
            employee=employee,
            type='dismissal',
            status=RequestStatus.PENDING,
        )

        # События нет
        assert not EmployeeAction.objects.filter(
            extra__request_id=request.id
        ).exists()

    def test_signal_not_fired_on_rejection(self, user_factory):
        """Сигнал не срабатывает при отклонении."""
        employee = user_factory()
        approver = user_factory()

        request = Request.objects.create(
            employee=employee,
            type='dismissal',
            status=RequestStatus.PENDING,
        )

        # Отклоняем
        request.status = RequestStatus.REJECTED
        request.approver = approver
        request.save()

        # События нет
        assert not EmployeeAction.objects.filter(
            extra__request_id=request.id
        ).exists()

    def test_unknown_request_type_no_action(self, user_factory):
        """Неизвестный тип заявки не создаёт события."""
        employee = user_factory()
        approver = user_factory()

        # Используем тип, который не в маппингах
        request = Request.objects.create(
            employee=employee,
            type='other',  # Не в IMMEDIATE/SCHEDULED маппингах
            status=RequestStatus.PENDING,
        )

        # Одобряем
        request.status = RequestStatus.APPROVED
        request.approver = approver
        request.save()

        # События нет
        assert not EmployeeAction.objects.filter(
            employee=employee,
            extra__request_id=request.id
        ).exists()

    def test_action_date_from_request_date_from(self, user_factory):
        """Дата события берётся из date_from заявки."""
        employee = user_factory()
        approver = user_factory()
        specific_date = date(2026, 6, 15)

        request = Request.objects.create(
            employee=employee,
            type='dismissal',
            status=RequestStatus.PENDING,
            date_from=specific_date,
        )

        # Одобряем
        request.status = RequestStatus.APPROVED
        request.approver = approver
        request.save()

        action = EmployeeAction.objects.get(
            employee=employee,
            action='dismissed',
            extra__request_id=request.id
        )

        # Проверяем дату (может быть datetime, поэтому берём .date())
        action_date = action.date.date() if hasattr(action.date, 'date') else action.date
        assert action_date == specific_date

    @patch('employees.signals._apply_action_effects')
    def test_effects_applied_for_immediate_actions(self, mock_apply, user_factory):
        """Эффекты применяются для немедленных действий."""
        employee = user_factory()
        approver = user_factory()

        request = Request.objects.create(
            employee=employee,
            type='dismissal',
            status=RequestStatus.PENDING,
        )

        # Одобряем
        request.status = RequestStatus.APPROVED
        request.approver = approver
        request.save()

        # Проверяем что _apply_action_effects была вызвана
        mock_apply.assert_called_once()
        created_action = mock_apply.call_args[0][0]
        assert created_action.action == 'dismissed'


@pytest.mark.django_db
class TestRequestMappings:
    """Тесты корректности маппингов типов заявок."""

    def test_immediate_mapping_complete(self):
        """Проверка что все немедленные маппинги правильные."""
        assert IMMEDIATE_ACTION_MAPPING == {
            'transfer': 'transferred',
            'dismissal': 'dismissed',
        }

    def test_scheduled_mapping_complete(self):
        """Проверка что все отложенные маппинги правильные."""
        assert SCHEDULED_ACTION_MAPPING == {
            'vacation': 'on_leave',
            'sick_leave': 'on_sick_leave',
        }

    def test_no_overlap_in_mappings(self):
        """Проверка что маппинги не пересекаются."""
        immediate_keys = set(IMMEDIATE_ACTION_MAPPING.keys())
        scheduled_keys = set(SCHEDULED_ACTION_MAPPING.keys())

        assert immediate_keys.isdisjoint(scheduled_keys), \
            "Request types должны быть либо immediate, либо scheduled, но не оба"
