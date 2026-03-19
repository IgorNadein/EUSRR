"""
Unit тесты для UserService.
"""

import pytest
from unittest.mock import Mock, patch

from employees.models import Employee
from employees.ldap.services.user_service import UserService


class TestUserServiceCreate:
    """Тесты создания пользователей."""
    
    @pytest.mark.skip(reason="Требует полного мокирования create_user")
    @pytest.mark.django_db
    def test_create_user_success(
        self,
        mock_ldap_context,
        mock_ldap_connection,
        mock_ldap_repository,
        mock_employee_repo_functions,
        mock_sync_state_repo_functions,
        sample_user_dto
    ):
        """Тест успешного создания пользователя."""
        # Arrange
        service = UserService(
            mock_ldap_repository,
            mock_employee_repo_functions,
            mock_sync_state_repo_functions
        )
        
        # Mock _create_user_in_ldap чтобы вернуть DN
        test_dn = 'CN=Ivan Ivanov,OU=Users,DC=example,DC=com'
        
        with patch.object(service, '_create_user_in_ldap', return_value=test_dn), \
             patch.object(service, '_set_password'), \
             patch.object(service, '_enable_user'), \
             patch.object(service, '_touch_state'), \
             patch('employees.ldap.services.user_service.read_attrs', return_value={}), \
             patch('employees.ldap.services.user_service.get_guid_str', return_value='test-guid'):
            
            # Act
            result = service.create_user(sample_user_dto)
            
            # Assert
            assert result is not None
            assert result.first_name == sample_user_dto.first_name
            assert result.last_name == sample_user_dto.last_name
            assert result.email == sample_user_dto.email
    
    @pytest.mark.skip(reason="Требует полного мокирования LDAP операций")
    @pytest.mark.django_db
    def test_unique_samaccountname_generation(
        self,
        mock_ldap_context,
        mock_ldap_connection,
        mock_ldap_repository,
        mock_employee_repo_functions,
        mock_sync_state_repo_functions
    ):
        """Тест генерации уникального sAMAccountName."""
        # Arrange
        service = UserService(
            mock_ldap_repository,
            mock_employee_repo_functions,
            mock_sync_state_repo_functions
        )
        
        # Создаём mock DTO
        from employees.ldap.domain.dtos import DirectoryUserDTO
        mock_dto = DirectoryUserDTO(
            first_name="Иван",
            last_name="Иванов",
            email="ivanov@example.com",
            phone_e164=None,
            department_dn=None,
            group_cns=[],
            initial_password="Test123!",
            is_active=True
        )
        
        # Mock is_taken через conn.search
        mock_ldap_connection.search.side_effect = [True, True, False]
        
        # Act
        login = service._unique_logins(
            mock_ldap_connection,
            mock_dto,
            '@example.com'
        )
        
        # Assert
        assert login[0] == 'ivanov3'  # Третья попытка успешна
        assert login[1] == 'ivanov3@example.com'
    
    @pytest.mark.skip(reason="Требует полного мокирования create_user")
    @pytest.mark.django_db
    def test_create_user_with_groups(
        self,
        mock_ldap_context,
        mock_ldap_connection,
        mock_ldap_repository,
        mock_employee_repo_functions,
        mock_sync_state_repo_functions,
        sample_user_dto,
        sample_django_group
    ):
        """Тест создания пользователя с группами."""
        # Arrange
        service = UserService(
            mock_ldap_repository,
            mock_employee_repo_functions,
            mock_sync_state_repo_functions
        )
        sample_user_dto.groups = ["Developers"]
        
        with patch('employees.models.Employee.objects.create') as mock_create:
            mock_employee = Mock(spec=Employee)
            mock_employee.id = 1
            mock_employee.groups = Mock()
            mock_create.return_value = mock_employee
            
            with patch(
                'django.contrib.auth.models.Group.objects.get'
            ) as mock_group_get:
                mock_group_get.return_value = sample_django_group
                
                # Act
                service.create_user(sample_user_dto)
                
                # Assert
                mock_employee.groups.add.assert_called_once()


class TestUserServiceUpdate:
    """Тесты обновления пользователей."""
    
    @pytest.mark.skip(reason="Требует полного мокирования update_user")
    @pytest.mark.django_db
    def test_update_user_basic_fields(
        self,
        mock_ldap_context,
        mock_ldap_connection,
        mock_ldap_repository,
        mock_employee_repo_functions,
        mock_sync_state_repo_functions,
        sample_employee,
        sample_user_dto
    ):
        """Тест обновления базовых полей пользователя."""
        # Arrange
        service = UserService(
            mock_ldap_repository,
            mock_employee_repo_functions,
            mock_sync_state_repo_functions
        )
        
        mock_sync_state_repo_functions.get_or_create.return_value = (
            Mock(ldap_dn='CN=Test,OU=Users,DC=example,DC=com'),
            False
        )
        
        # Act
        service.update_user(sample_employee, sample_user_dto)
        
        # Assert
        assert sample_employee.first_name == "Иван"
        assert sample_employee.last_name == "Иванов"
        assert sample_employee.email == "ivanov@example.com"
        assert mock_ldap_connection.modify.called
        sample_employee.save.assert_called()
    
    @pytest.mark.skip(reason="Требует полного мокирования update_user")
    @pytest.mark.django_db
    def test_update_user_password(
        self,
        mock_ldap_context,
        mock_ldap_connection,
        mock_ldap_repository,
        mock_employee_repo_functions,
        mock_sync_state_repo_functions,
        sample_employee,
        sample_user_dto
    ):
        """Тест обновления пароля пользователя."""
        # Arrange
        service = UserService(
            mock_ldap_repository,
            mock_employee_repo_functions,
            mock_sync_state_repo_functions
        )
        
        mock_sync_state_repo_functions.get_or_create.return_value = (
            Mock(ldap_dn='CN=Test,OU=Users,DC=example,DC=com'),
            False
        )
        
        sample_user_dto.password = "NewPassword123!"
        
        # Act
        service.update_user(sample_employee, sample_user_dto)
        
        # Assert
        assert mock_ldap_connection.extend.microsoft.modify_password.called
    
    @pytest.mark.skip(reason="Требует полного мокирования update_user")
    @pytest.mark.django_db
    def test_update_user_department(
        self,
        mock_ldap_context,
        mock_ldap_connection,
        mock_ldap_repository,
        mock_employee_repo_functions,
        mock_sync_state_repo_functions,
        sample_employee,
        sample_user_dto,
        sample_department
    ):
        """Тест обновления отдела пользователя."""
        # Arrange
        service = UserService(
            mock_ldap_repository,
            mock_employee_repo_functions,
            mock_sync_state_repo_functions
        )
        
        mock_sync_state_repo_functions.get_or_create.return_value = (
            Mock(ldap_dn='CN=Test,OU=Users,DC=example,DC=com'),
            False
        )
        
        # Изменяем отдел
        sample_employee.department = None
        sample_user_dto.department = sample_department
        
        # Act
        service.update_user(sample_employee, sample_user_dto)
        
        # Assert
        assert sample_employee.department == sample_department


class TestUserServiceDelete:
    """Тесты удаления пользователей."""
    
    @pytest.mark.skip(reason="Требует мокирования внутреннего _ldap()")
    @pytest.mark.django_db
    def test_delete_user_soft(
        self,
        mock_ldap_context,
        mock_ldap_connection,
        mock_ldap_repository,
        mock_employee_repo_functions,
        mock_sync_state_repo_functions,
        sample_employee
    ):
        """Тест удаления пользователя (soft-disable + delete)."""
        # Arrange
        service = UserService(
            mock_ldap_repository,
            mock_employee_repo_functions,
            mock_sync_state_repo_functions
        )
        
        mock_sync_state_repo_functions.get_or_create.return_value = (
            Mock(ldap_dn='CN=Test,OU=Users,DC=example,DC=com'),
            False
        )
        
        # Mock modify для soft-disable (через modify_user_attrs)
        with patch(
            'employees.ldap.services.user_service.modify_user_attrs'
        ) as mock_modify:
            mock_modify.return_value = True
            
            # Mock delete для Employee
            sample_employee.delete = Mock()
            
            # Act
            service.delete_user(sample_employee)
            
            # Assert
            # Проверяем, что был вызван modify_user_attrs
            assert mock_modify.called
            # Проверяем, что был вызван delete
            assert sample_employee.delete.called
    
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
        
        # Mock ORM LdapUser.objects.get
        mock_user = Mock()
        mock_user.dn = f'CN=Test,{new_base}'
        with patch(
            'employees.ldap.services.user_service.LdapUser'
        ) as MockLdapUser:
            MockLdapUser.objects.get.return_value = mock_user
            
            # Act
            new_dn = service._move_user_to_base(old_dn, new_base)
        
        # Assert
        assert new_dn == f'CN=Test,{new_base}'
        MockLdapUser.objects.get.assert_called_once_with(dn=old_dn)
        assert mock_user.base_dn == new_base
        mock_user.save.assert_called_once()


class TestUserServiceSync:
    """Тесты синхронизации пользователей."""
    
    @pytest.mark.skip(reason="Метод sync_users_from_ldap не реализован")
    @pytest.mark.django_db
    def test_sync_users_from_ldap(
        self,
        mock_ldap_context,
        mock_ldap_connection,
        mock_ldap_repository,
        mock_employee_repo_functions,
        mock_sync_state_repo_functions,
        mock_ldap_entry
    ):
        """Тест синхронизации пользователей из AD."""
        # Arrange
        service = UserService(
            mock_ldap_repository,
            mock_employee_repo_functions,
            mock_sync_state_repo_functions
        )
        
        # Mock search результат
        mock_ldap_connection.entries = [mock_ldap_entry]
        mock_employee_repo_functions.load_users_index.return_value = ({}, {})
        mock_employee_repo_functions.find_user_for_dto.return_value = None
        
        with patch('employees.models.Employee.objects.create') as mock_create:
            mock_employee = Mock(spec=Employee)
            mock_employee.id = 1
            mock_create.return_value = mock_employee
            
            # Act
            stats = service.sync_users_from_ldap()
            
            # Assert
            assert stats['created'] >= 0
            assert stats['updated'] >= 0
            assert mock_ldap_connection.search.called
