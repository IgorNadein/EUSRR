"""
Pytest конфигурация и фикстуры для тестирования LDAP модуля.
"""

import os

import pytest
from unittest.mock import Mock, patch
from django.contrib.auth.models import Group as DjangoGroup

from employees.models import Employee, Department, Position, LdapSyncState
from employees.ldap.domain.dtos import DirectoryUserDTO, DirectoryDepartmentDTO


# ==================== Mock LDAP Connection ====================

@pytest.fixture
def mock_ldap_connection():
    """Mock LDAP соединения для изоляции от реального AD."""
    conn = Mock()
    conn.result = {'description': 'success'}
    conn.entries = []

    # Mock базовых операций
    conn.add = Mock(return_value=True)
    conn.delete = Mock(return_value=True)
    conn.modify = Mock(return_value=True)
    conn.modify_dn = Mock(return_value=True)
    conn.search = Mock(return_value=True)

    # Mock extend для паролей
    conn.extend = Mock()
    conn.extend.microsoft = Mock()
    conn.extend.microsoft.modify_password = Mock(return_value=True)

    return conn


@pytest.fixture
def mock_ldap_context(mock_ldap_connection):
    """Mock контекстного менеджера _ldap() во всех сервисах."""
    targets = [
        'employees.ldap.infrastructure.connections._ldap',
        'employees.ldap.services.group_service._ldap',
        'employees.ldap.services.department_service._ldap',
        'employees.ldap.services.user_service._ldap',
        'employees.ldap.services.position_service._ldap',
    ]
    patches = []
    for target in targets:
        try:
            p = patch(target)
            mock = p.start()
            mock.return_value.__enter__.return_value = mock_ldap_connection
            mock.return_value.__exit__.return_value = None
            patches.append(p)
        except (AttributeError, ModuleNotFoundError):
            pass
    yield patches[0] if patches else None
    for p in patches:
        p.stop()


# ==================== Django Models Fixtures ====================

@pytest.fixture
def sample_employee(db):
    """Создает тестового сотрудника."""
    return Employee.objects.create(
        first_name="Иван",
        last_name="Иванов",
        email="ivanov@example.com",
        is_active=True
    )


@pytest.fixture
def sample_department(db):
    """Создает тестовый отдел."""
    return Department.objects.create(
        name="IT Отдел",
        description="IT Department"
    )


@pytest.fixture
def sample_position(db):
    """Создает тестовую должность (без LDAP синхронизации)."""
    from employees.signals.ldap.position import sync_position_to_ldap_on_save
    from django.db.models.signals import post_save

    # Отключаем LDAP синхронизацию при создании Position
    post_save.disconnect(sync_position_to_ldap_on_save, sender=Position)
    try:
        pos = Position.objects.create(
            name="Разработчик",
            description="Backend разработчик"
        )
    finally:
        post_save.connect(sync_position_to_ldap_on_save, sender=Position)
    return pos


@pytest.fixture
def sample_django_group(db):
    """Создает тестовую Django группу."""
    return DjangoGroup.objects.create(name="Developers")


@pytest.fixture
def sample_ldap_sync_state(db, sample_employee):
    """Создает тестовую запись синхронизации."""
    return LdapSyncState.objects.create(
        model='employee',
        object_pk=str(sample_employee.id),
        ldap_dn='CN=Иван Иванов,OU=Users,DC=example,DC=com'
    )


# ==================== DTO Fixtures ====================

@pytest.fixture
def sample_user_dto():
    """Создает тестовый DTO для пользователя."""
    return DirectoryUserDTO(
        first_name="Иван",
        last_name="Иванов",
        email="ivanov@example.com",
        phone_e164="+79001234567",
        department_dn="OU=IT,DC=example,DC=com",
        group_cns=["Developers", "Users"],
        initial_password="Test123456!",
        avatar_bytes=None,
        is_active=True
    )


@pytest.fixture
def sample_department_dto():
    """Создает тестовый DTO для отдела."""
    return DirectoryDepartmentDTO(
        name="IT Отдел",
        description="IT Department",
        head=None
    )


# ==================== Mock Repositories ====================

@pytest.fixture
def mock_ldap_repository():
    """Mock LdapRepository."""
    repo = Mock()
    repo.read_attrs = Mock(return_value={'cn': ['Test User']})
    repo.is_taken = Mock(return_value=False)
    repo.modify_attrs = Mock(return_value=True)
    repo.ensure_container_exists = Mock(return_value=True)
    repo.modify_or_ignore = Mock(return_value=True)
    return repo


@pytest.fixture
def mock_employee_repo_functions():
    """Mock функций employee_repository."""
    ns = Mock()
    ns.load_users_index = Mock(return_value=({}, {}))
    ns.find_user_for_dto = Mock(return_value=None)
    ns.bind_user_department = Mock(return_value=None)
    ns.get_stale_employee_ids = Mock(return_value=[])
    return ns


@pytest.fixture
def mock_sync_state_repo_functions():
    """Mock функций sync_state_repository."""
    ns = Mock()
    ns.get_or_create = Mock()
    ns.touch = Mock()
    ns.get_employees_with_dn = Mock(return_value=Employee.objects.none())
    ns.delete_for_employee = Mock()
    return ns


# ==================== Mock Services ====================

@pytest.fixture
def mock_user_service():
    """Mock UserService для тестирования других сервисов."""
    service = Mock()
    service.create_user = Mock()
    service.update_user = Mock()
    service.delete_user = Mock()
    service._get_employee_dn = Mock(
        return_value='CN=Test User,OU=Users,DC=example,DC=com'
    )
    service._move_user_to_base = Mock(
        return_value='CN=Test User,OU=NewBase,DC=example,DC=com'
    )
    return service


@pytest.fixture
def mock_group_service():
    """Mock GroupService для тестирования других сервисов."""
    service = Mock()
    dn = 'CN=Test Group,OU=Groups,DC=example,DC=com'
    service.create = Mock(return_value=dn)
    service.delete = Mock()
    service.rename = Mock()
    service.set_description = Mock()
    service.add_members = Mock()
    service.remove_members = Mock()
    service.replace_members = Mock()
    service.list_members = Mock(return_value=[])
    service.find_dn = Mock(return_value=dn)
    service.groups_with_member = Mock(return_value=set())
    return service


@pytest.fixture
def mock_department_service():
    """Mock DepartmentService для тестирования."""
    service = Mock()
    service.create_department = Mock()
    service.update_department = Mock()
    service.delete_department = Mock()
    service.add_member = Mock()
    service.remove_member = Mock()
    service.set_head = Mock()
    service._get_department_dn = Mock(
        return_value='OU=Test Department,DC=example,DC=com'
    )
    return service


@pytest.fixture
def mock_position_service():
    """Mock PositionService для тестирования."""
    service = Mock()
    service.reconcile_position = Mock()
    service.assign_position = Mock()
    service.unassign_position = Mock()
    service.delete_position_group = Mock()
    return service


# ==================== LDAP Entry Mocks ====================

@pytest.fixture
def mock_ldap_entry():
    """Mock LDAP entry объекта."""
    entry = Mock()
    entry.entry_dn = 'CN=Test User,OU=Users,DC=example,DC=com'
    entry.cn = Mock()
    entry.cn.value = 'Test User'
    entry.mail = Mock()
    entry.mail.value = 'test@example.com'
    entry.objectGUID = Mock()
    # Mock GUID (16 bytes)
    guid_bytes = (
        b'\x01\x02\x03\x04\x05\x06\x07\x08'
        b'\x09\x0a\x0b\x0c\x0d\x0e\x0f\x10'
    )
    entry.objectGUID.value = guid_bytes
    return entry


# ==================== Settings Overrides ====================

@pytest.fixture
def ldap_test_settings(settings):
    """Тестовые настройки LDAP."""
    settings.LDAP_HOST = 'ldaps://test.example.com:636'
    settings.LDAP_BASE_DN = 'DC=example,DC=com'
    settings.LDAP_BIND_DN = 'CN=TestUser,DC=example,DC=com'
    settings.LDAP_BIND_PASSWORD = os.getenv(
        'LDAP_BIND_PASSWORD',
        'test-ldap-bind-password',
    )
    settings.LDAP_GROUPS_BASE = 'OU=Groups,DC=example,DC=com'
    settings.LDAP_POSITIONS_BASE = 'OU=Positions,DC=example,DC=com'
    settings.LDAP_UPN_SUFFIX = '@example.com'
    return settings


# ==================== Helper Functions ====================

def create_mock_ldap_entry(dn, attributes=None):
    """
    Создает mock LDAP entry с заданными атрибутами.

    Args:
        dn: Distinguished Name
        attributes: Словарь атрибутов {attr_name: value}

    Returns:
        Mock объект LDAP entry
    """
    entry = Mock()
    entry.entry_dn = dn

    if attributes:
        for attr_name, attr_value in attributes.items():
            attr_mock = Mock()
            attr_mock.value = attr_value
            setattr(entry, attr_name, attr_mock)

    return entry


def assert_ldap_operation_called(mock_conn, operation, dn=None):
    """
    Проверяет, что LDAP операция была вызвана.

    Args:
        mock_conn: Mock LDAP соединения
        operation: Название операции ('add', 'delete', 'modify', etc.)
        dn: Ожидаемый DN (опционально)
    """
    op_mock = getattr(mock_conn, operation)
    assert op_mock.called, f"LDAP операция '{operation}' не была вызвана"

    if dn and op_mock.call_args:
        called_dn = op_mock.call_args[0][0]
        assert called_dn == dn, f"Ожидался DN '{dn}', получен '{called_dn}'"
