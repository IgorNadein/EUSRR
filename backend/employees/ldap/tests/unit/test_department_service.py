"""
Unit тесты для DepartmentService.
"""

import pytest
from unittest.mock import Mock, patch

from employees.ldap.services.department_service import DepartmentService


class TestDepartmentServiceHelpers:
    """Тесты вспомогательных методов."""

    @pytest.mark.django_db
    def test_get_department_dn(
        self,
        mock_ldap_repository,
        mock_group_service,
        mock_user_service,
        sample_department,
        sample_ldap_sync_state
    ):
        """Тест получения DN отдела."""
        # Arrange
        service = DepartmentService(
            mock_group_service,
            mock_user_service
        )

        # Mock sync state chain
        expected_dn = 'OU=IT,DC=example,DC=com'
        with patch(
            'employees.ldap.services.department_service.LdapSyncState.objects'
        ) as mock_objects:
            mock_filter = Mock()
            mock_values_list = Mock()
            mock_filter.values_list.return_value = mock_values_list
            mock_values_list.first.return_value = expected_dn
            mock_objects.filter.return_value = mock_filter

            # Act
            dn = service._get_department_dn(sample_department)

            # Assert
            assert dn == expected_dn
            assert 'OU=' in dn
            assert 'IT' in dn

    @pytest.mark.django_db
    def test_get_department_by_dn(
        self,
        mock_ldap_repository,
        mock_group_service,
        mock_user_service,
        sample_department
    ):
        """Тест поиска отдела по DN."""
        # Arrange
        service = DepartmentService(
            mock_group_service,
            mock_user_service
        )

        dn = 'OU=IT,DC=example,DC=com'

        # Mock LdapSyncState query chain
        with patch(
            'employees.ldap.services.department_service.LdapSyncState.objects'
        ) as mock_sync_objects:
            mock_filter = Mock()
            mock_values_list = Mock()
            mock_filter.values_list.return_value = mock_values_list
            mock_values_list.first.return_value = str(sample_department.pk)
            mock_sync_objects.filter.return_value = mock_filter

            # Mock Department.objects query
            with patch(
                'employees.ldap.services.department_service.Department.objects'
            ) as mock_dept_objects:
                mock_dept_filter = Mock()
                mock_dept_filter.first.return_value = sample_department
                mock_dept_objects.filter.return_value = mock_dept_filter

                # Act
                result = service._get_department_by_dn(dn)

                # Assert
                assert result == sample_department

    @pytest.mark.django_db
    def test_reconcile_department_group(
        self,
        mock_ldap_repository,
        mock_group_service,
        mock_user_service,
        sample_department
    ):
        """Тест синхронизации группы отдела."""
        # Arrange
        service = DepartmentService(
            mock_group_service,
            mock_user_service
        )

        dept_dn = 'OU=IT,DC=example,DC=com'

        # Mock EmployeeDepartment
        with patch(
            'employees.ldap.services.department_service.EmployeeDepartment'
        ) as mock_emp_dept:
            mock_query = mock_emp_dept.objects.filter.return_value
            mock_query.values_list.return_value = [1, 2]

            with patch(
                'employees.ldap.services.department_service.LdapSyncState.objects'
            ) as mock_sync_objects:
                mock_sync_filter = Mock()
                mock_sync_filter.values_list.return_value = [
                    ('1', 'CN=One,OU=Users,DC=example,DC=com'),
                    ('2', 'CN=Two,OU=Users,DC=example,DC=com'),
                ]
                mock_sync_objects.filter.return_value = mock_sync_filter

                mock_group = Mock()

                with patch.object(
                    service,
                    '_ensure_department_group',
                    return_value='CN=DEP_IT,DC=example,DC=com'
                ):
                    with patch(
                        'employees.ldap.services.department_service.'
                        'LdapOrganizationalUnitGroup.objects.get',
                        return_value=mock_group
                    ):
                        # Act
                        result = service._reconcile_department_group(
                            sample_department,
                            dept_dn
                        )

                        # Assert
                        assert 'DEP_' in result
                        assert mock_group.member == [
                            'CN=One,OU=Users,DC=example,DC=com',
                            'CN=Two,OU=Users,DC=example,DC=com',
                        ]
                        assert mock_group.save.called
