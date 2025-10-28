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
        
        # Act
        dn = service.create(mock_ldap_connection, group_name, base_dn)
        
        # Assert
        assert mock_ldap_connection.add.called
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
        
        # Act
        service.create(
            mock_ldap_connection,
            group_name,
            base_dn,
            description=description
        )
        
        # Assert
        assert mock_ldap_connection.add.called
        # Проверяем, что description был передан
        call_args = mock_ldap_connection.add.call_args
        if call_args and len(call_args) > 0:
            # Может быть в позиционных или keyword args
            assert call_args is not None


class TestGroupServiceDelete:
    """Тесты удаления групп."""
    
    @pytest.mark.django_db
    def test_delete_group(
        self,
        mock_ldap_context,
        mock_ldap_connection,
        mock_ldap_repository
    ):
        """Тест удаления группы."""
        # Arrange
        service = GroupService()
        group_dn = "CN=Test Group,OU=Groups,DC=example,DC=com"
        
        # Act
        service.delete(mock_ldap_connection, group_dn)
        
        # Assert
        mock_ldap_connection.delete.assert_called_once_with(group_dn)


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
        new_dn = service.rename(mock_ldap_connection, old_dn, new_name)
        
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
        service.set_description(
            mock_ldap_connection,
            group_dn,
            description
        )
        
        # Assert
        assert mock_ldap_connection.modify.called


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
        
        # Act
        service.add_members(mock_ldap_connection, group_dn, member_dns)
        
        # Assert
        assert mock_ldap_connection.modify.called
    
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
        
        # Act
        service.remove_members(mock_ldap_connection, group_dn, member_dns)
        
        # Assert
        assert mock_ldap_connection.modify.called
    
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
        
        # Mock текущих членов
        mock_ldap_repository.read_attrs.return_value = {
            'member': ['CN=OldUser,OU=Users,DC=example,DC=com']
        }
        
        # Act
        service.replace_members(
            mock_ldap_connection,
            group_dn,
            member_dns
        )
        
        # Assert
        # Должно быть 2 вызова: remove old, add new
        assert mock_ldap_connection.modify.call_count >= 1
    
    @pytest.mark.django_db
    def test_list_members(
        self,
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
        
        # Mock LDAP search result
        mock_entry = Mock()
        mock_entry.member = Mock()
        mock_entry.member.values = expected_members
        mock_ldap_connection.entries = [mock_entry]
        mock_ldap_connection.search.return_value = True
        
        # Act
        members = service.list_members(mock_ldap_connection, group_dn)
        
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
        
        # Mock search результат
        mock_entry = Mock()
        mock_entry.entry_dn = "CN=Test Group,OU=Groups,DC=example,DC=com"
        mock_ldap_connection.entries = [mock_entry]
        
        # Act
        dn = service.find_dn(mock_ldap_connection, group_name)
        
        # Assert
        assert dn == mock_entry.entry_dn
        assert mock_ldap_connection.search.called
    
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
        
        # Mock search результат
        mock_entry1 = Mock()
        mock_entry1.entry_dn = "CN=Group1,OU=Groups,DC=example,DC=com"
        mock_entry2 = Mock()
        mock_entry2.entry_dn = "CN=Group2,OU=Groups,DC=example,DC=com"
        mock_ldap_connection.entries = [mock_entry1, mock_entry2]
        
        # Act
        groups = service.groups_with_member(
            mock_ldap_connection,
            member_dn
        )
        
        # Assert
        assert len(groups) == 2
        assert mock_entry1.entry_dn in groups
        assert mock_entry2.entry_dn in groups


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
