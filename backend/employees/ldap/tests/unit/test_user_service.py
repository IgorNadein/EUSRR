"""
Unit тесты для UserService.
"""

import pytest
from unittest.mock import Mock

from employees.ldap.services.user_service import UserService


class TestUserServiceCreate:
    """Тесты создания пользователей."""


class TestUserServiceUpdate:
    """Тесты обновления пользователей."""


class TestUserServiceDelete:
    """Тесты удаления пользователей."""

    @pytest.mark.django_db
    def test_delete_user_hard(
        self,
        mock_ldap_context,
        mock_ldap_connection,
        mock_ldap_repository,
        mock_employee_repo_functions,
        mock_sync_state_repo_functions,
        sample_employee
    ):
        """Тест удаления без DN (пропускаем soft-disable)."""
        # Arrange
        service = UserService(
            mock_ldap_repository,
            mock_employee_repo_functions,
            mock_sync_state_repo_functions
        )

        # Mock: DN не найден
        mock_sync_state_repo_functions.get_or_create.return_value = (
            Mock(ldap_dn=None),
            False
        )

        # Mock delete для Employee
        sample_employee.delete = Mock()

        # Act
        service.delete_user(sample_employee)

        # Assert
        # Проверяем, что modify не вызывался (нет DN)
        assert not mock_ldap_connection.modify.called
        # Проверяем, что delete был вызван
        assert sample_employee.delete.called


class TestUserServiceHelpers:
    """Тесты вспомогательных методов."""

    @pytest.mark.django_db
    def test_employee_ids_to_dns(
        self,
        mock_ldap_repository,
        mock_employee_repo_functions,
        mock_sync_state_repo_functions,
        sample_employee,
        sample_ldap_sync_state
    ):
        """Тест конвертации ID сотрудников в DN."""
        # Arrange
        service = UserService(
            mock_ldap_repository,
            mock_employee_repo_functions,
            mock_sync_state_repo_functions
        )

        mock_sync_state_repo_functions.get_employees_with_dn.return_value = [
            (sample_employee.id, sample_ldap_sync_state.ldap_dn)
        ]

        # Act
        result = service.employee_ids_to_dns([sample_employee.id])

        # Assert
        assert len(result) == 1
        assert result[0] == sample_ldap_sync_state.ldap_dn

    @pytest.mark.django_db
    def test_get_employee_dn(
        self,
        mock_ldap_repository,
        mock_employee_repo_functions,
        mock_sync_state_repo_functions,
        sample_employee,
        sample_ldap_sync_state
    ):
        """Тест получения DN сотрудника."""
        # Arrange
        service = UserService(
            mock_ldap_repository,
            mock_employee_repo_functions,
            mock_sync_state_repo_functions
        )

        mock_sync_state_repo_functions.get_or_create.return_value = (
            sample_ldap_sync_state,
            False
        )

        # Act
        dn = service._get_employee_dn(sample_employee)

        # Assert
        assert dn == sample_ldap_sync_state.ldap_dn

    @pytest.mark.django_db
    def test_move_user_to_base(
        self,
        mock_ldap_context,
        mock_ldap_connection,
        mock_ldap_repository,
        mock_employee_repo_functions,
        mock_sync_state_repo_functions,
        sample_employee,
        sample_ldap_sync_state
    ):
        """Тест перемещения пользователя в другой OU."""
        # Arrange
        service = UserService(
            mock_ldap_repository,
            mock_employee_repo_functions,
            mock_sync_state_repo_functions
        )

        old_dn = 'CN=Test,OU=OldBase,DC=example,DC=com'
        new_base = 'OU=NewBase,DC=example,DC=com'

        # Mock conn.modify_dn для low-level перемещения
        mock_ldap_connection.modify_dn.return_value = True

        # Act
        new_dn = service._move_user_to_base(mock_ldap_connection, old_dn, new_base)

        # Assert
        assert new_dn == f'CN=Test,{new_base}'
        mock_ldap_connection.modify_dn.assert_called_once_with(
            old_dn, 'CN=Test', new_superior=new_base
        )


class TestUserServiceSync:
    """Тесты синхронизации пользователей."""
