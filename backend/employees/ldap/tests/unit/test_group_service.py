"""
Unit тесты для GroupService.
"""

import pytest
from unittest.mock import Mock, patch

from employees.ldap.services.group_service import GroupService


class TestGroupServiceCreate:
    """Тесты создания групп."""
    
    @pytest.mark.django_db
    def test_create_group_success(
        self,
        mock_ldap_context,
        mock_ldap_connection,
        mock_ldap_repository
    ):
        """Тест успешного создания группы."""
        # Arrange
        service = GroupService()
        group_name = "Test Group"
        base_dn = "OU=Groups,DC=example,DC=com"
        
        # Act — ORM создаёт через LdapGroup.objects.create()
        # mock_ldap_context патчит _ldap() для внутренних вызовов
        with patch('employees.ldap.services.group_service.LdapGroup') as MockLdapGroup:
            dn = service.create(group_name, parent_dn=base_dn)
        
        # Assert
        assert "CN=Test Group" in dn
        assert "OU=Groups" in dn
    
    @pytest.mark.django_db
    def test_create_group_with_description(
        self,
        mock_ldap_context,
        mock_ldap_connection,
        mock_ldap_repository
    ):
        """Тест создания группы с описанием."""
        # Arrange
        service = GroupService()
        group_name = "Developers"
        base_dn = "OU=Groups,DC=example,DC=com"
        description = "Development team"
        
        # Act — ORM создаёт через LdapGroup.objects.create()
        with patch('employees.ldap.services.group_service.LdapGroup') as MockLdapGroup:
            service.create(
                group_name,
                parent_dn=base_dn,
                description=description
            )
        
        # Assert
        MockLdapGroup.objects.create.assert_called_once()


class TestGroupServiceDelete:
    """Тесты удаления групп."""
    
    @pytest.mark.django_db
    def test_delete_group(
        self,
        mock_ldap_context,
        mock_ldap_connection,
        mock_ldap_repository
    ):
        """Тест удаления группы через ORM."""
        # Arrange
        service = GroupService()
        group_dn = "CN=Test Group,OU=Groups,DC=example,DC=com"
        
        mock_group = Mock()
        with patch(
            'employees.ldap.services.group_service.LdapGroup'
        ) as MockLdapGroup:
            MockLdapGroup.objects.get.return_value = mock_group
            
            # Act
            service.delete(group_dn)
        
        # Assert
        MockLdapGroup.objects.get.assert_called_once_with(dn=group_dn)
        mock_group.delete.assert_called_once()


class TestGroupServiceModify:
    """Тесты модификации групп."""
    
    @pytest.mark.django_db
    def test_rename_group(
        self,
        mock_ldap_context,
        mock_ldap_connection,
        mock_ldap_repository
    ):
        """Тест переименования группы."""
        # Arrange
        service = GroupService()
        old_dn = "CN=Old Name,OU=Groups,DC=example,DC=com"
        new_name = "New Name"
        
        # Act
        new_dn = service.rename(old_dn, new_name)
        
        # Assert
        assert mock_ldap_connection.modify_dn.called
        assert "CN=New Name" in new_dn
    
    @pytest.mark.django_db
    def test_set_description(
        self,
        mock_ldap_context,
        mock_ldap_connection,
        mock_ldap_repository
    ):
        """Тест изменения описания группы."""
        # Arrange
        service = GroupService()
        group_dn = "CN=Test,OU=Groups,DC=example,DC=com"
        description = "Updated description"
        
        # Act
        with patch('employees.ldap.services.group_service.LdapGroup') as MockLdapGroup:
            mock_group = Mock()
            MockLdapGroup.objects.get.return_value = mock_group
            service.set_description(
                group_dn,
                description
            )
        
        # Assert
        mock_group.save.assert_called_once()


class TestGroupServiceMembers:
    """Тесты управления членами группы."""
    
    @pytest.mark.django_db
    def test_add_members(
        self,
        mock_ldap_context,
        mock_ldap_connection,
        mock_ldap_repository
    ):
        """Тест добавления членов в группу."""
        # Arrange
        service = GroupService()
        group_dn = "CN=Test,OU=Groups,DC=example,DC=com"
        member_dns = [
            "CN=User1,OU=Users,DC=example,DC=com",
            "CN=User2,OU=Users,DC=example,DC=com"
        ]
        
        # Mock ORM
        mock_group = Mock()
        mock_group.member = []
        with patch(
            'employees.ldap.services.group_service.LdapGroup'
        ) as MockLdapGroup:
            MockLdapGroup.objects.get.return_value = mock_group
            
            # Act
            service.add_members(group_dn, member_dns)
        
        # Assert
        assert mock_group.member == member_dns
        mock_group.save.assert_called_once()
    
    @pytest.mark.django_db
    def test_remove_members(
        self,
        mock_ldap_context,
        mock_ldap_connection,
        mock_ldap_repository
    ):
        """Тест удаления членов из группы."""
        # Arrange
        service = GroupService()
        group_dn = "CN=Test,OU=Groups,DC=example,DC=com"
        member_dns = ["CN=User1,OU=Users,DC=example,DC=com"]
        
        # Mock ORM — группа содержит удаляемого участника
        mock_group = Mock()
        mock_group.member = ["CN=User1,OU=Users,DC=example,DC=com"]
        with patch(
            'employees.ldap.services.group_service.LdapGroup'
        ) as MockLdapGroup:
            MockLdapGroup.objects.get.return_value = mock_group
            
            # Act
            service.remove_members(group_dn, member_dns)
        
        # Assert
        assert mock_group.member == []
        mock_group.save.assert_called_once()
    
    @pytest.mark.django_db
    def test_replace_members(
        self,
        mock_ldap_context,
        mock_ldap_connection,
        mock_ldap_repository
    ):
        """Тест замены всех членов группы."""
        # Arrange
        service = GroupService()
        group_dn = "CN=Test,OU=Groups,DC=example,DC=com"
        member_dns = ["CN=User1,OU=Users,DC=example,DC=com"]
        
        # Mock ORM — группа с текущими участниками
        mock_group = Mock()
        mock_group.member = ['CN=OldUser,OU=Users,DC=example,DC=com']
        with patch(
            'employees.ldap.services.group_service.LdapGroup'
        ) as MockLdapGroup:
            MockLdapGroup.objects.get.return_value = mock_group
            
            # Act
            service.replace_members(group_dn, member_dns)
        
        # Assert
        assert mock_group.member == member_dns
        mock_group.save.assert_called_once()
    
    @pytest.mark.django_db
    def test_list_members(
        self,
        mock_ldap_context,
        mock_ldap_connection,
        mock_ldap_repository
    ):
        """Тест получения списка членов группы."""
        # Arrange
        service = GroupService()
        group_dn = "CN=Test,OU=Groups,DC=example,DC=com"
        expected_members = [
            "CN=User1,OU=Users,DC=example,DC=com",
            "CN=User2,OU=Users,DC=example,DC=com"
        ]
        
        # Mock ORM
        mock_group = Mock()
        mock_group.member = expected_members
        with patch(
            'employees.ldap.services.group_service.LdapGroup'
        ) as MockLdapGroup:
            MockLdapGroup.objects.get.return_value = mock_group
            
            # Act
            members = service.list_members(group_dn)
        
        # Assert
        assert len(members) == 2
        assert members == expected_members


class TestGroupServiceSearch:
    """Тесты поиска групп."""
    
    @pytest.mark.django_db
    def test_find_dn(
        self,
        mock_ldap_context,
        mock_ldap_connection,
        mock_ldap_repository
    ):
        """Тест поиска DN группы по имени."""
        # Arrange
        service = GroupService()
        group_name = "Test Group"
        
        # Act  — find_dn использует ORM (LdapGroup.objects.filter)
        with patch('employees.ldap.services.group_service.LdapGroup') as MockLdapGroup:
            mock_group = Mock()
            mock_group.dn = "CN=Test Group,OU=Groups,DC=example,DC=com"
            MockLdapGroup.objects.filter.return_value.first.return_value = mock_group
            
            dn = service.find_dn(group_name)
        
        # Assert
        assert dn == mock_group.dn
    
    @pytest.mark.django_db
    def test_groups_with_member(
        self,
        mock_ldap_context,
        mock_ldap_connection,
        mock_ldap_repository
    ):
        """Тест поиска групп, в которых состоит пользователь."""
        # Arrange
        service = GroupService()
        member_dn = "CN=User,OU=Users,DC=example,DC=com"
        
        # Act  — groups_with_member использует ORM (LdapUser.objects.get)
        with patch('employees.ldap.services.group_service.LdapUser') as MockLdapUser:
            mock_user = Mock()
            mock_user.member_of = [
                "CN=Group1,OU=Groups,DC=example,DC=com",
                "CN=Group2,OU=Groups,DC=example,DC=com"
            ]
            MockLdapUser.objects.get.return_value = mock_user
            
            groups = service.groups_with_member(member_dn)
        
        # Assert
        assert len(groups) == 2


class TestGroupServiceSync:
    """Тесты синхронизации групп."""
    
    @pytest.mark.django_db
    def test_sync_catalog(
        self,
        mock_ldap_context,
        mock_ldap_connection,
        mock_ldap_repository,
        sample_django_group
    ):
        """Тест синхронизации каталога групп из AD в Django."""
        # Arrange
        service = GroupService()
        
        # Mock AD группы
        mock_entry = Mock()
        mock_entry.cn = Mock()
        mock_entry.cn.value = "Developers"
        mock_ldap_connection.entries = [mock_entry]
        
        with patch('django.contrib.auth.models.Group.objects') as mock_groups:
            mock_groups.all.return_value = [sample_django_group]
            
            with patch('django.core.cache.cache') as mock_cache:
                mock_cache.get.return_value = 0
                mock_cache.add.return_value = True
                
                # Act
                result = service.sync_catalog(
                    throttle_seconds=0,
                    delete_absent=False
                )
                
                # Assert
                # Проверяем, что метод отработал
                assert result >= 0
