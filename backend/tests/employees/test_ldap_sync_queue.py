"""Тесты LDAP sync queue — модель, задачи, сигналы.

Запуск:
    .venv/bin/python -m pytest tests/employees/test_ldap_sync_queue.py -v
"""

from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from django.test import override_settings
from django.utils import timezone


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def queue_item(db):
    """Создаёт LdapSyncQueue запись."""
    from employees.models import LdapSyncQueue

    return LdapSyncQueue.objects.create(
        operation="employee_save",
        model_name="employee",
        object_pk="42",
        payload={"object_pk": "42", "created": False, "changes": {"first_name": "Test"}},
    )


# ---------------------------------------------------------------------------
# Модель LdapSyncQueue
# ---------------------------------------------------------------------------

class TestLdapSyncQueueModel:

    def test_create_defaults(self, queue_item):
        from employees.models import LdapSyncQueue

        assert queue_item.status == LdapSyncQueue.Status.PENDING
        assert queue_item.attempts == 0
        assert queue_item.max_attempts == 5
        assert queue_item.next_retry_at is None

    def test_schedule_retry_increments_attempts(self, queue_item):
        queue_item.schedule_retry("connection timeout")
        queue_item.refresh_from_db()

        assert queue_item.attempts == 1
        assert queue_item.last_error == "connection timeout"
        assert queue_item.next_retry_at is not None
        assert queue_item.next_retry_at > timezone.now()

    def test_schedule_retry_marks_failed_after_max(self, queue_item):
        from employees.models import LdapSyncQueue

        queue_item.attempts = queue_item.max_attempts - 1
        queue_item.save()

        queue_item.schedule_retry("final failure")
        queue_item.refresh_from_db()

        assert queue_item.status == LdapSyncQueue.Status.FAILED

    def test_exponential_backoff(self, queue_item):
        """Проверяем, что delay растёт экспоненциально."""
        queue_item.schedule_retry("err1")
        retry1 = queue_item.next_retry_at

        queue_item.status = "pending"
        queue_item.save()
        queue_item.schedule_retry("err2")
        retry2 = queue_item.next_retry_at

        # Второй retry должен быть значительно позже первого
        assert retry2 > retry1

    def test_mark_completed(self, queue_item):
        from employees.models import LdapSyncQueue

        queue_item.mark_completed()
        queue_item.refresh_from_db()

        assert queue_item.status == LdapSyncQueue.Status.COMPLETED

    def test_str_repr(self, queue_item):
        s = str(queue_item)
        assert "pending" in s
        assert "employee_save" in s


# ---------------------------------------------------------------------------
# _enqueue helper
# ---------------------------------------------------------------------------

class TestEnqueue:

    @override_settings(CELERY_TASK_ALWAYS_EAGER=True)
    def test_enqueue_creates_record(self, db):
        from employees.models import LdapSyncQueue
        from employees.signals.ldap._queue import _enqueue

        with patch("employees.tasks.process_ldap_queue_item") as mock_task:
            mock_task.delay = MagicMock()
            item = _enqueue("employee_save", "employee", "99", {
                "object_pk": "99", "changes": {},
            })

        assert LdapSyncQueue.objects.filter(pk=item.pk).exists()
        assert item.operation == "employee_save"
        assert item.model_name == "employee"
        assert item.object_pk == "99"

    def test_enqueue_survives_celery_down(self, db):
        """Если Celery недоступен, запись всё равно создаётся в БД."""
        from employees.models import LdapSyncQueue
        from employees.signals.ldap._queue import _enqueue

        with patch("employees.tasks.process_ldap_queue_item") as mock_task:
            mock_task.delay.side_effect = Exception("Celery down")
            item = _enqueue("employee_save", "employee", "100", {
                "object_pk": "100", "changes": {},
            })

        assert LdapSyncQueue.objects.filter(pk=item.pk).exists()


# ---------------------------------------------------------------------------
# Celery tasks
# ---------------------------------------------------------------------------

class TestProcessQueueItem:

    @override_settings(LDAP_ENABLED=True)
    def test_successful_execution(self, queue_item):
        from employees.tasks import process_ldap_queue_item, _EXECUTORS
        from employees.models import LdapSyncQueue

        with patch.dict(_EXECUTORS, {"employee_save": MagicMock()}):
            process_ldap_queue_item(queue_item.pk)

        queue_item.refresh_from_db()
        assert queue_item.status == LdapSyncQueue.Status.COMPLETED

    @override_settings(LDAP_ENABLED=True)
    def test_failed_execution_retries(self, queue_item):
        from employees.tasks import process_ldap_queue_item, _EXECUTORS
        from employees.models import LdapSyncQueue

        mock_executor = MagicMock(side_effect=Exception("LDAP timeout"))
        with patch.dict(_EXECUTORS, {"employee_save": mock_executor}):
            process_ldap_queue_item(queue_item.pk)

        queue_item.refresh_from_db()
        assert queue_item.attempts == 1
        assert queue_item.status == LdapSyncQueue.Status.PENDING
        assert queue_item.next_retry_at is not None

    @override_settings(LDAP_ENABLED=False)
    def test_skips_when_ldap_disabled(self, queue_item):
        from employees.tasks import process_ldap_queue_item
        from employees.models import LdapSyncQueue

        process_ldap_queue_item(queue_item.pk)

        queue_item.refresh_from_db()
        # Не тронут — LDAP отключен
        assert queue_item.status == LdapSyncQueue.Status.PENDING

    @override_settings(LDAP_ENABLED=True)
    def test_unknown_operation(self, db):
        from employees.models import LdapSyncQueue
        from employees.tasks import process_ldap_queue_item

        item = LdapSyncQueue.objects.create(
            operation="unknown_op",
            model_name="test",
            object_pk="1",
            payload={},
        )
        process_ldap_queue_item(item.pk)

        item.refresh_from_db()
        assert item.status == LdapSyncQueue.Status.FAILED
        assert "Unknown operation" in item.last_error

    @override_settings(LDAP_ENABLED=True)
    def test_nonexistent_item(self, db):
        from employees.tasks import process_ldap_queue_item
        # Не должно падать
        process_ldap_queue_item(999999)


class TestProcessQueue:

    @override_settings(LDAP_ENABLED=True)
    def test_dispatches_pending_items(self, db):
        from employees.models import LdapSyncQueue
        from employees.tasks import process_ldap_queue

        LdapSyncQueue.objects.create(
            operation="employee_save",
            model_name="employee",
            object_pk="1",
            payload={"object_pk": "1", "changes": {}},
        )
        LdapSyncQueue.objects.create(
            operation="employee_save",
            model_name="employee",
            object_pk="2",
            payload={"object_pk": "2", "changes": {}},
        )

        with patch("employees.tasks.process_ldap_queue_item") as mock_task:
            mock_task.delay = MagicMock()
            process_ldap_queue()

        assert mock_task.delay.call_count == 2

    @override_settings(LDAP_ENABLED=True)
    def test_skips_future_retry(self, db):
        from employees.models import LdapSyncQueue
        from employees.tasks import process_ldap_queue

        LdapSyncQueue.objects.create(
            operation="employee_save",
            model_name="employee",
            object_pk="1",
            payload={},
            next_retry_at=timezone.now() + timedelta(hours=1),
        )

        with patch("employees.tasks.process_ldap_queue_item") as mock_task:
            mock_task.delay = MagicMock()
            process_ldap_queue()

        # Не подхватывает — retry ещё не наступил
        mock_task.delay.assert_not_called()


class TestDepartmentQueueExecutors:

    @override_settings(LDAP_ENABLED=True)
    def test_department_member_retry_reconciles_active_membership(
        self, db, user_factory
    ):
        from employees.models import Department, EmployeeDepartment, LdapSyncQueue
        from employees.tasks import process_ldap_queue_item

        with override_settings(LDAP_ENABLED=False):
            employee = user_factory(email="member-active@example.com")
            department = Department.objects.create(name="Dept Active Queue")
            link = EmployeeDepartment.objects.create(
                employee=employee,
                department=department,
                is_active=True,
            )

        item = LdapSyncQueue.objects.create(
            operation="department_member",
            model_name="employee_department",
            object_pk=str(link.pk),
            payload={
                "employee_pk": str(employee.pk),
                "department_pk": str(department.pk),
                "is_active": True,
                "role": None,
            },
        )

        with patch(
            "employees.ldap.services.department_service.DepartmentService.sync_member_state"
        ) as mock_sync:
            process_ldap_queue_item(item.pk)

        item.refresh_from_db()
        assert item.status == LdapSyncQueue.Status.COMPLETED
        mock_sync.assert_called_once_with(
            employee,
            department,
            is_active=True,
            role=None,
        )

    @override_settings(LDAP_ENABLED=True)
    def test_department_member_retry_reconciles_inactive_membership(
        self, db, user_factory
    ):
        from employees.models import Department, EmployeeDepartment, LdapSyncQueue
        from employees.tasks import process_ldap_queue_item

        with override_settings(LDAP_ENABLED=False):
            employee = user_factory(email="member-inactive@example.com")
            department = Department.objects.create(name="Dept Inactive Queue")
            link = EmployeeDepartment.objects.create(
                employee=employee,
                department=department,
                is_active=False,
            )

        item = LdapSyncQueue.objects.create(
            operation="department_member",
            model_name="employee_department",
            object_pk=str(link.pk),
            payload={
                "employee_pk": str(employee.pk),
                "department_pk": str(department.pk),
                "is_active": False,
                "role": None,
            },
        )

        with patch(
            "employees.ldap.services.department_service.DepartmentService.sync_member_state"
        ) as mock_sync:
            process_ldap_queue_item(item.pk)

        item.refresh_from_db()
        assert item.status == LdapSyncQueue.Status.COMPLETED
        mock_sync.assert_called_once_with(
            employee,
            department,
            is_active=False,
            role=None,
        )

    @override_settings(LDAP_ENABLED=True)
    def test_department_save_retry_uses_canonical_sync(
        self, db, user_factory
    ):
        from employees.models import Department, LdapSyncQueue
        from employees.tasks import process_ldap_queue_item

        with override_settings(LDAP_ENABLED=False):
            head = user_factory(email="dept-head-queue@example.com")
            department = Department.objects.create(
                name="Dept Queue Original",
                description="old description",
            )
            department.name = "Dept Queue Updated"
            department.description = "new description"
            department.head = head
            department.save(update_fields=["name", "description", "head"])

        item = LdapSyncQueue.objects.create(
            operation="department_save",
            model_name="department",
            object_pk=str(department.pk),
            payload={
                "object_pk": str(department.pk),
                "created": False,
                "changes": {
                    "name": "Dept Queue Updated",
                    "description": "new description",
                },
                "sync_head": True,
            },
        )

        with patch(
            "employees.ldap.services.department_service.DepartmentService.sync_department_state"
        ) as mock_sync:
            process_ldap_queue_item(item.pk)

        item.refresh_from_db()
        assert item.status == LdapSyncQueue.Status.COMPLETED
        mock_sync.assert_called_once_with(
            department,
            created=False,
            changes={
                "name": "Dept Queue Updated",
                "description": "new description",
            },
            sync_head=True,
        )


# ---------------------------------------------------------------------------
# Сигналы: проверка enqueue при ошибке LDAP
# ---------------------------------------------------------------------------

class TestSignalEnqueue:

    @override_settings(LDAP_ENABLED=True)
    def test_employee_save_enqueues_on_ldap_error(self, db):
        """При DirectoryLdapError в сигнале employee save — операция попадает в очередь."""
        from employees.models import LdapSyncQueue, LdapSyncState
        from employees.signals.ldap.employee import sync_employee_to_ldap_on_save
        from employees.ldap.errors import DirectoryLdapError

        # Создаём stub Employee
        emp = MagicMock()
        emp.pk = 1
        emp.id = 1
        emp.is_ldap_managed = True
        emp._skip_ldap_sync = False
        emp._ldap_changes = {"first_name": "New"}
        emp._ldap_avatar = None

        # hasattr / delattr support
        _attrs = {"_ldap_changes", "_ldap_avatar", "_skip_ldap_sync"}
        original_hasattr = hasattr

        # Создаём sync state
        LdapSyncState.objects.create(
            model="employee", object_pk="1", ldap_dn="CN=test,DC=example,DC=com",
        )

        with patch("employees.signals.ldap.employee.UserService") as MockSvc:
            MockSvc.return_value.update_user.side_effect = DirectoryLdapError("conn refused")
            with patch("employees.tasks.process_ldap_queue_item"):
                sync_employee_to_ldap_on_save(
                    sender=MagicMock(), instance=emp, created=False,
                )

        assert LdapSyncQueue.objects.filter(
            operation="employee_save", object_pk="1",
        ).exists()

    @override_settings(LDAP_ENABLED=True)
    def test_employee_delete_enqueues_on_ldap_error(self, db):
        """При ошибке удаления — операция попадает в очередь."""
        from employees.models import LdapSyncQueue
        from employees.signals.ldap.employee import sync_employee_to_ldap_on_delete
        from employees.ldap.errors import DirectoryLdapError

        emp = MagicMock()
        emp.pk = 2
        emp.id = 2
        emp.is_ldap_managed = True

        with patch("employees.signals.ldap.employee.UserService") as MockSvc:
            MockSvc.return_value.delete_user.side_effect = DirectoryLdapError("conn refused")
            with patch("employees.tasks.process_ldap_queue_item"):
                sync_employee_to_ldap_on_delete(
                    sender=MagicMock(), instance=emp,
                )

        assert LdapSyncQueue.objects.filter(
            operation="employee_delete", object_pk="2",
        ).exists()

    @override_settings(LDAP_ENABLED=True)
    def test_position_save_enqueues_on_ldap_error(self, db):
        """При ошибке синхронизации Position — попадает в очередь."""
        from employees.models import LdapSyncQueue
        from employees.signals.ldap.position import sync_position_to_ldap_on_save
        from employees.ldap.errors import DirectoryLdapError

        pos = MagicMock()
        pos.pk = 5
        pos.id = 5
        pos.name = "Developer"
        pos._skip_ldap_sync = False

        with patch("employees.signals.ldap.position.PositionService") as MockSvc:
            MockSvc.return_value.reconcile_position.side_effect = DirectoryLdapError("timeout")
            with patch("employees.tasks.process_ldap_queue_item"):
                sync_position_to_ldap_on_save(
                    sender=MagicMock(), instance=pos, created=True,
                )

        assert LdapSyncQueue.objects.filter(
            operation="position_save", object_pk="5",
        ).exists()
