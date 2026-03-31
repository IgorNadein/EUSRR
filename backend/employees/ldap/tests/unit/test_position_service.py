"""
Unit тесты для PositionService.
"""

import pytest
from unittest.mock import Mock, patch
from django.conf import settings

from employees.models import Position, Employee
from employees.ldap.services.position_service import PositionService


class TestPositionServiceReconcile:
    """Тесты синхронизации должностей."""

    @pytest.mark.django_db
    def test_reconcile_position(
        self,
        mock_ldap_context,
        mock_ldap_connection,
        mock_group_service,
        mock_user_service,
        sample_position
    ):
        """Тест синхронизации должности."""
        # Arrange
        service = PositionService(mock_group_service, mock_user_service)

        # Mock QuerySet для сотрудников с должностью
        mock_queryset = Mock()
        mock_queryset.values_list.return_value = [1, 2, 3]

        with patch.object(
            Employee.objects,
            'filter',
            return_value=mock_queryset
        ):
            with patch.object(
                mock_user_service,
                '_employee_ids_to_dns',
                return_value=['CN=User,OU=Users,DC=example,DC=com']
            ):
                with patch.object(
                    service,
                    '_ensure_position_group',
                    return_value='CN=POS_1,OU=Positions,DC=example,DC=com'
                ):
                    # Act
                    service.reconcile_position(sample_position)

                    # Assert
                    assert mock_group_service.replace_members.called

    @pytest.mark.django_db
    def test_reconcile_position_nesting(
        self,
        mock_ldap_context,
        mock_ldap_connection,
        mock_group_service,
        mock_user_service,
        sample_position
    ):
        """Тест синхронизации вложенности должностей."""
        # Arrange
        service = PositionService(mock_group_service, mock_user_service)

        # Создаем родительскую должность
        parent_position = Position.objects.create(
            name="Senior Developer",
            description="Senior position"
        )

        # Используем patch для groups.all() вместо прямого присваивания
        mock_group_queryset = Mock()
        mock_group_queryset.__iter__ = Mock(return_value=iter([]))

        with patch.object(
            sample_position.groups,
            'all',
            return_value=mock_group_queryset
        ):
            sample_position.parent = parent_position

            pos_dn = (
                f'CN=POS_{sample_position.id},OU=Positions,DC=example,DC=com'
            )
            parent_dn = (
                f'CN=POS_{parent_position.id},OU=Positions,DC=example,DC=com'
            )

            # Mock поиск текущих групп
            mock_ldap_connection.search.return_value = False
            mock_ldap_connection.entries = []

            with patch.object(
                service,
                '_ensure_position_group',
                side_effect=[pos_dn, parent_dn]
            ):
                # Act
                service._reconcile_position_nesting(
                    mock_ldap_connection,
                    sample_position
                )

                # Assert - проверяем, что метод отработал
                assert service._ensure_position_group.called


class TestPositionServiceAssign:
    """Тесты назначения/снятия должностей."""

    @pytest.mark.django_db
    def test_assign_position(
        self,
        mock_group_service,
        mock_user_service,
        sample_position,
        sample_employee
    ):
        """Тест назначения должности сотруднику."""
        # Arrange
        service = PositionService(mock_group_service, mock_user_service)

        pos_dn = f'CN=POS_{sample_position.id},OU=Positions,DC=example,DC=com'
        user_dn = 'CN=User,OU=Users,DC=example,DC=com'

        with patch.object(
            service,
            '_ensure_position_group',
            return_value=pos_dn
        ):
            with patch.object(
                mock_user_service,
                '_get_employee_dn',
                return_value=user_dn
            ):
                # Act
                service.assign_position(sample_employee, sample_position)

                # Assert
                # add_members вызывается с conn (внутри используется _ldap())
                assert mock_group_service.add_members.called
                # Проверяем, что pos_dn и user_dn в аргументах
                call_args = mock_group_service.add_members.call_args
                assert pos_dn in str(call_args)
                assert user_dn in str(call_args)

    @pytest.mark.django_db
    def test_unassign_position(
        self,
        mock_group_service,
        mock_user_service,
        sample_position,
        sample_employee
    ):
        """Тест снятия должности с сотрудника."""
        # Arrange
        service = PositionService(mock_group_service, mock_user_service)

        pos_dn = f'CN=POS_{sample_position.id},OU=Positions,DC=example,DC=com'
        user_dn = 'CN=User,OU=Users,DC=example,DC=com'

        with patch.object(
            service,
            '_ensure_position_group',
            return_value=pos_dn
        ):
            with patch.object(
                mock_user_service,
                '_get_employee_dn',
                return_value=user_dn
            ):
                # Act
                service.unassign_position(sample_employee, sample_position)

                # Assert
                assert mock_group_service.remove_members.called
                call_args = mock_group_service.remove_members.call_args
                assert pos_dn in str(call_args)
                assert user_dn in str(call_args)


class TestPositionServiceDelete:
    """Тесты удаления должностей."""

    @pytest.mark.django_db
    def test_delete_position_group(
        self,
        mock_ldap_context,
        mock_ldap_connection,
        mock_group_service,
        mock_user_service,
        sample_position
    ):
        """Тест удаления группы должности из AD."""
        # Arrange
        service = PositionService(mock_group_service, mock_user_service)

        pos_dn = f'CN=POS_{sample_position.id},OU=Positions,DC=example,DC=com'
        sample_position.ldap_group_dn = pos_dn

        # Mock: нет родительских групп
        mock_group_service.groups_with_member.return_value = []

        # Mock ORM LdapGroup.objects.get().delete()
        mock_group = Mock()
        with patch(
            'employees.ldap.orm_models.LdapGroup'
        ) as MockLdapGroup:
            MockLdapGroup.objects.get.return_value = mock_group

            # Act
            service.delete_position_group(sample_position)

        # Assert
        MockLdapGroup.objects.get.assert_called_once_with(dn=pos_dn)
        mock_group.delete.assert_called_once()

    @pytest.mark.django_db
    def test_delete_nonexistent_position_group(
        self,
        mock_ldap_context,
        mock_ldap_connection,
        mock_group_service,
        mock_user_service,
        sample_position
    ):
        """Тест удаления несуществующей группы должности."""
        # Arrange
        service = PositionService(mock_group_service, mock_user_service)
        # ldap_group_dn пустой — сервис должен выйти раньше
        sample_position.ldap_group_dn = ""

        with patch(
            'employees.ldap.orm_models.LdapGroup'
        ) as MockLdapGroup:
            # Act
            service.delete_position_group(sample_position)

            # Assert — не должно быть попытки удаления
            assert not MockLdapGroup.objects.get.called


class TestPositionServiceHelpers:
    """Тесты вспомогательных методов."""

    @pytest.mark.django_db
    def test_positions_base(
        self,
        mock_group_service,
        mock_user_service,
        ldap_test_settings
    ):
        """Тест получения базового DN для должностей."""
        # Arrange
        service = PositionService(mock_group_service, mock_user_service)

        # Act
        base = service._positions_base()

        # Assert
        assert 'OU=Positions' in base
        assert ldap_test_settings.LDAP_BASE_DN in base

    @pytest.mark.django_db
    def test_ensure_positions_base(
        self,
        mock_ldap_context,
        mock_ldap_connection,
        mock_ldap_repository,
        mock_group_service,
        mock_user_service
    ):
        """Тест создания базового OU для должностей."""
        # Arrange
        service = PositionService(mock_group_service, mock_user_service)

        # Mock LdapRepository в месте использования
        with patch(
            'employees.ldap.services.position_service.ensure_container_exists'
        ):
            # Act
            result = service._ensure_positions_base(mock_ldap_connection)

            # Assert
            assert result == settings.LDAP_POSITIONS_BASE

    @pytest.mark.django_db
    def test_ensure_position_group(
        self,
        mock_ldap_context,
        mock_ldap_connection,
        mock_group_service,
        mock_user_service,
        sample_position
    ):
        """Тест создания/получения группы должности."""
        # Arrange
        service = PositionService(mock_group_service, mock_user_service)

        expected_name = f"POS_{sample_position.name}"
        expected_dn = (
            f'CN={expected_name},'
            f'{settings.LDAP_POSITIONS_BASE}'
        )

        # Mock: saved_dn существует и найден в LDAP
        sample_position.ldap_group_dn = expected_dn

        # conn.search возвращает True (saved_dn найден)
        mock_entry = Mock()
        mock_entry.entry_dn = expected_dn
        mock_ldap_connection.search.return_value = True
        mock_ldap_connection.entries = [mock_entry]

        # Mock LdapRepository
        with patch(
            'employees.ldap.services.position_service.ensure_container_exists'
        ):
            # Act
            dn = service._ensure_position_group(
                mock_ldap_connection,
                sample_position
            )

            # Assert
            assert expected_name in dn
            assert dn == expected_dn

    @pytest.mark.django_db
    def test_ensure_position_group_create(
        self,
        mock_ldap_context,
        mock_ldap_connection,
        mock_group_service,
        mock_user_service,
        sample_position
    ):
        """Тест создания новой группы должности."""
        # Arrange
        service = PositionService(mock_group_service, mock_user_service)

        expected_name = f"POS_{sample_position.name}"

        # Mock: ldap_group_dn пустой
        sample_position.ldap_group_dn = ""

        # Mock: группа не найдена при поиске
        mock_ldap_connection.search.return_value = False
        mock_ldap_connection.entries = []

        # Mock ensure_container_exists + conn.add (low-level create)
        mock_ldap_connection.add.return_value = True
        with patch(
            'employees.ldap.services.position_service.ensure_container_exists'
        ):
            # Act
            dn = service._ensure_position_group(
                mock_ldap_connection,
                sample_position
            )

            # Assert
            assert expected_name in dn
            # Проверяем, что conn.add был вызван (low-level создание)
            mock_ldap_connection.add.assert_called_once()
