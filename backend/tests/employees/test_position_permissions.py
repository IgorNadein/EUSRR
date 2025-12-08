"""
Тесты прав доступа через должности (Position + Groups).

Проверяют, что:
1. Пользователь с должностью получает права из групп должности
2. PositionRoleBackend корректно добавляет права через get_all_permissions
3. has_perm работает для прав из должностей
4. Права наследуются при назначении/изменении должности
"""
import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType

from employees.models import Position

User = get_user_model()

pytestmark = pytest.mark.django_db


# ============================================================================
# Фикстуры (на уровне модуля, доступны всем тестам)
# ============================================================================

@pytest.fixture
def feed_content_type():
    """ContentType для приложения feed (для прав публикаций)."""
    ct, _ = ContentType.objects.get_or_create(
        app_label="feed", model="post"
    )
    return ct


@pytest.fixture
def documents_content_type():
    """ContentType для приложения documents."""
    ct, _ = ContentType.objects.get_or_create(
        app_label="documents", model="document"
    )
    return ct


@pytest.fixture
def group_with_publish_perm(feed_content_type):
    """Группа с правом публикации в feed."""
    group = Group.objects.create(name="publishers")
    
    # Ищем существующее право или создаём новое
    perm = Permission.objects.filter(
        codename="publish_company_post",
        content_type=feed_content_type,
    ).first()
    
    if not perm:
        perm = Permission.objects.create(
            codename="publish_company_post",
            name="Can publish company post",
            content_type=feed_content_type,
        )
    
    group.permissions.add(perm)
    return group


@pytest.fixture
def group_with_document_perm(documents_content_type):
    """Группа с правом добавления документов."""
    group = Group.objects.create(name="doc_creators")
    
    # Ищем существующее право или используем defaults
    perm = Permission.objects.filter(
        codename="add_document",
        content_type=documents_content_type,
    ).first()
    
    if not perm:
        perm = Permission.objects.create(
            codename="add_document",
            name="Can add document",
            content_type=documents_content_type,
        )
    
    group.permissions.add(perm)
    return group


@pytest.fixture
def engineer_position(group_with_publish_perm, group_with_document_perm):
    """Должность 'Инженер' с двумя группами прав."""
    position = Position.objects.create(
        name="Инженер",
        description="Технический специалист",
    )
    position.groups.add(
        group_with_publish_perm, group_with_document_perm
    )
    return position


@pytest.fixture
def manager_position(group_with_publish_perm):
    """Должность 'Менеджер' только с правом публикации."""
    position = Position.objects.create(
        name="Менеджер",
        description="Управленец",
    )
    position.groups.add(group_with_publish_perm)
    return position


@pytest.fixture
def basic_user(user_factory):
    """Обычный пользователь без должности и прав."""
    return user_factory(
        email="user@example.com",
        staff=False,
        superuser=False,
        verified=True,
        active=True,
    )


# ============================================================================
# Тесты
# ============================================================================

class TestPositionPermissions:
    """Тесты прав доступа через должности."""

    def test_user_without_position_has_no_permissions(self, basic_user):
        """Пользователь без должности не имеет прав."""
        assert not basic_user.has_perm("feed.publish_company_post")
        assert not basic_user.has_perm("documents.add_document")
        
        # Проверяем через get_all_permissions
        all_perms = basic_user.get_all_permissions()
        assert "feed.publish_company_post" not in all_perms
        assert "documents.add_document" not in all_perms

    def test_user_with_position_gets_permissions(
        self, basic_user, engineer_position
    ):
        """Пользователь с должностью получает права из групп должности."""
        # Назначаем должность
        basic_user.position = engineer_position
        basic_user.save()
        
        # Обновляем пользователя из БД (чтобы подтянуть связи)
        basic_user.refresh_from_db()
        
        # Проверяем has_perm
        assert basic_user.has_perm("feed.publish_company_post"), \
            "Должен быть доступ к публикации (из группы publishers)"
        assert basic_user.has_perm("documents.add_document"), \
            "Должен быть доступ к созданию документов (из группы doc_creators)"
        
        # Проверяем через get_all_permissions
        all_perms = basic_user.get_all_permissions()
        assert "feed.publish_company_post" in all_perms, \
            f"Право должно быть в all_perms. Текущие права: {all_perms}"
        assert "documents.add_document" in all_perms, \
            f"Право должно быть в all_perms. Текущие права: {all_perms}"

    def test_position_change_updates_permissions(
        self, basic_user, engineer_position, manager_position
    ):
        """При смене должности права обновляются."""
        # Назначаем инженера (2 права)
        basic_user.position = engineer_position
        basic_user.save()
        
        # Получаем fresh instance чтобы сбросить кэш прав
        user_id = basic_user.id
        basic_user = User.objects.get(id=user_id)
        
        assert basic_user.has_perm("feed.publish_company_post")
        assert basic_user.has_perm("documents.add_document")
        
        # Меняем на менеджера (только 1 право)
        basic_user.position = manager_position
        basic_user.save()
        
        # Снова получаем fresh instance
        basic_user = User.objects.get(id=user_id)
        
        assert basic_user.has_perm("feed.publish_company_post"), \
            "Право на публикацию должно остаться"
        assert not basic_user.has_perm("documents.add_document"), \
            "Право на документы должно исчезнуть"

    def test_remove_position_removes_permissions(
        self, basic_user, engineer_position
    ):
        """При снятии должности права удаляются."""
        # Назначаем должность
        basic_user.position = engineer_position
        basic_user.save()
        
        # Получаем fresh instance
        user_id = basic_user.id
        basic_user = User.objects.get(id=user_id)
        
        assert basic_user.has_perm("feed.publish_company_post")
        assert basic_user.has_perm("documents.add_document")
        
        # Снимаем должность
        basic_user.position = None
        basic_user.save()
        
        # Снова fresh instance для сброса кэша
        basic_user = User.objects.get(id=user_id)
        
        assert not basic_user.has_perm("feed.publish_company_post"), \
            "Права должны исчезнуть после снятия должности"
        assert not basic_user.has_perm("documents.add_document"), \
            "Права должны исчезнуть после снятия должности"

    def test_multiple_users_with_same_position(
        self, user_factory, engineer_position
    ):
        """Несколько пользователей с одной должностью получают
        одинаковые права.
        """
        user1 = user_factory(email="user1@example.com")
        user2 = user_factory(email="user2@example.com")
        
        user1.position = engineer_position
        user2.position = engineer_position
        user1.save()
        user2.save()
        
        user1.refresh_from_db()
        user2.refresh_from_db()
        
        # Оба должны иметь одинаковые права
        for user in [user1, user2]:
            assert user.has_perm("feed.publish_company_post")
            assert user.has_perm("documents.add_document")

    def test_superuser_has_all_permissions(
        self, user_factory, engineer_position
    ):
        """is_superuser имеет все права независимо от должности."""
        superuser = user_factory(email="admin@example.com", superuser=True)
        
        # Без должности superuser имеет все права
        assert superuser.has_perm("feed.publish_company_post")
        assert superuser.has_perm("documents.add_document")
        assert superuser.has_perm("any.random_permission")
        
        # С должностью тоже все права
        superuser.position = engineer_position
        superuser.save()
        superuser = User.objects.get(id=superuser.id)
        
        assert superuser.has_perm("feed.publish_company_post")
        assert superuser.has_perm("documents.add_document")
        assert superuser.has_perm("any.random_permission")

    def test_position_group_permissions_are_additive(
        self, basic_user, feed_content_type
    ):
        """Если у должности несколько групп, права суммируются."""
        # Создаём две группы с разными правами
        group1 = Group.objects.create(name="group1")
        perm1 = Permission.objects.filter(
            codename="perm1",
            content_type=feed_content_type,
        ).first()
        if not perm1:
            perm1 = Permission.objects.create(
                codename="perm1",
                name="Permission 1",
                content_type=feed_content_type,
            )
        group1.permissions.add(perm1)
        
        group2 = Group.objects.create(name="group2")
        perm2 = Permission.objects.filter(
            codename="perm2",
            content_type=feed_content_type,
        ).first()
        if not perm2:
            perm2 = Permission.objects.create(
                codename="perm2",
                name="Permission 2",
                content_type=feed_content_type,
            )
        group2.permissions.add(perm2)
        
        # Создаём должность с обеими группами
        position = Position.objects.create(name="Multi-group Position")
        position.groups.add(group1, group2)
        
        basic_user.position = position
        basic_user.save()
        basic_user.refresh_from_db()
        
        # Пользователь должен иметь права из обеих групп
        assert basic_user.has_perm("feed.perm1")
        assert basic_user.has_perm("feed.perm2")

    def test_get_all_permissions_includes_position_perms(
        self, basic_user, engineer_position
    ):
        """get_all_permissions() включает права из должности."""
        basic_user.position = engineer_position
        basic_user.save()
        basic_user.refresh_from_db()
        
        all_perms = basic_user.get_all_permissions()
        
        # Проверяем, что это set
        assert isinstance(all_perms, set)
        
        # Проверяем содержимое
        assert "feed.publish_company_post" in all_perms
        assert "documents.add_document" in all_perms
        
        # Проверяем, что нет дубликатов (set гарантирует это)
        perms_list = list(all_perms)
        assert len(perms_list) == len(set(perms_list))


class TestPositionPermissionsEdgeCases:
    """Тесты граничных случаев и edge cases."""

    @pytest.fixture
    def empty_position(self):
        """Должность без групп."""
        return Position.objects.create(
            name="Empty Position",
            description="Должность без прав",
        )

    def test_position_without_groups_grants_no_permissions(
        self, user_factory, empty_position
    ):
        """Должность без групп не даёт прав."""
        user = user_factory(email="user@example.com")
        user.position = empty_position
        user.save()
        user.refresh_from_db()
        
        all_perms = user.get_all_permissions()
        assert len(all_perms) == 0, "Должность без групп не должна давать прав"

    def test_inactive_user_has_no_permissions(
        self, user_factory, engineer_position
    ):
        """Неактивный пользователь не имеет прав даже с должностью."""
        user = user_factory(email="inactive@example.com", active=False)
        user.position = engineer_position
        user.save()
        
        # Получаем fresh instance
        user = User.objects.get(id=user.id)
        
        # is_active=False блокирует все права
        assert not user.has_perm("feed.publish_company_post")
        assert not user.has_perm("documents.add_document")

    def test_position_permissions_with_direct_user_permissions(
        self, user_factory, engineer_position, feed_content_type
    ):
        """Права из должности + прямые права пользователя объединяются."""
        user = user_factory(email="user@example.com")
        
        # Даём пользователю прямое право
        direct_perm, _ = Permission.objects.get_or_create(
            codename="direct_perm",
            name="Direct Permission",
            content_type=feed_content_type,
        )
        user.user_permissions.add(direct_perm)
        
        # Назначаем должность
        user.position = engineer_position
        user.save()
        user.refresh_from_db()
        
        # Должен иметь и прямые права, и права из должности
        assert user.has_perm("feed.direct_perm"), \
            "Прямое право должно работать"
        assert user.has_perm("feed.publish_company_post"), \
            "Право из должности должно работать"
        assert user.has_perm("documents.add_document"), \
            "Право из должности должно работать"


class TestPositionPermissionsIntegration:
    """Интеграционные тесты с реальными моделями приложения."""

    def test_feed_permissions_through_position(
        self, user_factory, feed_content_type
    ):
        """Проверка прав на публикацию постов через должность."""
        # Создаём группу с правами публикации
        publishers = Group.objects.create(name="publishers")
        
        for codename in ["publish_company_post", "publish_department_post"]:
            perm, _ = Permission.objects.get_or_create(
                codename=codename,
                name=f"Can {codename.replace('_', ' ')}",
                content_type=feed_content_type,
            )
            publishers.permissions.add(perm)
        
        # Создаём должность редактора
        editor_position = Position.objects.create(name="Редактор")
        editor_position.groups.add(publishers)
        
        # Назначаем пользователю
        user = user_factory(email="editor@example.com")
        user.position = editor_position
        user.save()
        user.refresh_from_db()
        
        # Проверяем права
        assert user.has_perm("feed.publish_company_post")
        assert user.has_perm("feed.publish_department_post")

    def test_documents_permissions_through_position(
        self, user_factory, documents_content_type
    ):
        """Проверка прав на документы через должность."""
        # Создаём группу с правами на документы
        doc_managers = Group.objects.create(name="doc_managers")
        
        for codename in [
            "add_document", "change_document",
            "delete_document", "view_document"
        ]:
            # Используем filter().first() вместо get_or_create
            perm = Permission.objects.filter(
                codename=codename,
                content_type=documents_content_type,
            ).first()
            
            if not perm:
                perm = Permission.objects.create(
                    codename=codename,
                    name=f"Can {codename.replace('_', ' ')}",
                    content_type=documents_content_type,
                )
            
            doc_managers.permissions.add(perm)
        
        # Создаём должность документоведа
        doc_position = Position.objects.create(name="Документовед")
        doc_position.groups.add(doc_managers)
        
        # Назначаем пользователю
        user = user_factory(email="docs@example.com")
        user.position = doc_position
        user.save()
        user.refresh_from_db()
        
        # Проверяем все CRUD права
        assert user.has_perm("documents.add_document")
        assert user.has_perm("documents.change_document")
        assert user.has_perm("documents.delete_document")
        assert user.has_perm("documents.view_document")
