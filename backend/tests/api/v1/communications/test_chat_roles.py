"""
Тесты для системы ролей в чатах (ChatMembership)

Тестирует:
- Создание участников с разными ролями
- Изменение ролей участников
- Права доступа для каждой роли (admin, moderator, member, guest)
- Ограничения и запреты (владелец, невалидные роли и т.д.)
- Отправку сообщений в зависимости от роли
- Управление участниками в зависимости от роли
- Закрепление сообщений в зависимости от роли
"""

import pytest
from communications.models import Chat, ChatMembership, Message
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APIClient

User = get_user_model()
pytestmark = pytest.mark.django_db


# ==================== Fixtures ====================


@pytest.fixture
def owner(db):
    """Владелец чата"""
    return User.objects.create_user(
        email="owner@test.com",
        password="testpass123",
        first_name="Chat",
        last_name="Owner",
        phone_number="+79991111111",
        send_activation_email=False,
    )


@pytest.fixture
def admin_user(db):
    """Пользователь с ролью admin"""
    return User.objects.create_user(
        email="admin@test.com",
        password="testpass123",
        first_name="Admin",
        last_name="User",
        phone_number="+79992222222",
        send_activation_email=False,
    )


@pytest.fixture
def moderator_user(db):
    """Пользователь с ролью moderator"""
    return User.objects.create_user(
        email="moderator@test.com",
        password="testpass123",
        first_name="Moderator",
        last_name="User",
        phone_number="+79993333333",
        send_activation_email=False,
    )


@pytest.fixture
def member_user(db):
    """Пользователь с ролью member"""
    return User.objects.create_user(
        email="member@test.com",
        password="testpass123",
        first_name="Member",
        last_name="User",
        phone_number="+79994444444",
        send_activation_email=False,
    )


@pytest.fixture
def guest_user(db):
    """Пользователь с ролью guest"""
    return User.objects.create_user(
        email="guest@test.com",
        password="testpass123",
        first_name="Guest",
        last_name="User",
        phone_number="+79995555555",
        send_activation_email=False,
    )


@pytest.fixture
def regular_user(db):
    """Обычный пользователь (не участник чата)"""
    return User.objects.create_user(
        email="regular@test.com",
        password="testpass123",
        first_name="Regular",
        last_name="User",
        phone_number="+79996666666",
        send_activation_email=False,
    )


@pytest.fixture
def group_chat_with_roles(owner, admin_user, moderator_user, member_user, guest_user):
    """Групповой чат с участниками разных ролей"""
    chat = Chat.objects.create(
        type="group",
        name="Test Group Chat",
        description="Chat for testing roles",
        created_by=owner
    )
    
    # Добавляем владельца
    chat.participants.add(owner)
    
    # Добавляем участников с разными ролями
    chat.participants.add(admin_user, moderator_user, member_user, guest_user)
    
    # Создаем memberships с соответствующими ролями
    ChatMembership.objects.create(
        chat=chat,
        user=admin_user,
        role='admin',
        invited_by=owner
    )
    
    ChatMembership.objects.create(
        chat=chat,
        user=moderator_user,
        role='moderator',
        invited_by=owner
    )
    
    ChatMembership.objects.create(
        chat=chat,
        user=member_user,
        role='member',
        invited_by=owner
    )
    
    ChatMembership.objects.create(
        chat=chat,
        user=guest_user,
        role='guest',
        invited_by=owner
    )
    
    return chat


@pytest.fixture
def owner_client(owner):
    """Аутентифицированный клиент для владельца"""
    client = APIClient()
    client.force_authenticate(user=owner)
    return client


@pytest.fixture
def admin_client(admin_user):
    """Аутентифицированный клиент для админа"""
    client = APIClient()
    client.force_authenticate(user=admin_user)
    return client


@pytest.fixture
def moderator_client(moderator_user):
    """Аутентифицированный клиент для модератора"""
    client = APIClient()
    client.force_authenticate(user=moderator_user)
    return client


@pytest.fixture
def member_client(member_user):
    """Аутентифицированный клиент для обычного участника"""
    client = APIClient()
    client.force_authenticate(user=member_user)
    return client


@pytest.fixture
def guest_client(guest_user):
    """Аутентифицированный клиент для гостя"""
    client = APIClient()
    client.force_authenticate(user=guest_user)
    return client


@pytest.fixture
def regular_client(regular_user):
    """Аутентифицированный клиент для обычного пользователя"""
    client = APIClient()
    client.force_authenticate(user=regular_user)
    return client


# ==================== Тесты получения информации о ролях ====================


class TestChatMembershipRetrieval:
    """Тесты получения информации о членстве и ролях"""
    
    def test_get_chat_includes_memberships(self, owner_client, group_chat_with_roles):
        """Проверка что API возвращает информацию о memberships"""
        url = f"/api/v1/communications/chats/{group_chat_with_roles.id}/"
        response = owner_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        # Проверяем наличие поля memberships
        assert 'memberships' in data
        assert isinstance(data['memberships'], list)
        
        # Должно быть 4 membership (admin, moderator, member, guest)
        assert len(data['memberships']) == 4
        
        # Проверяем структуру данных membership
        for membership in data['memberships']:
            assert 'id' in membership
            assert 'user' in membership
            assert 'user_name' in membership
            assert 'role' in membership
            assert 'joined_at' in membership
            assert 'can_send_messages' in membership
            assert 'can_add_members' in membership
            assert 'can_remove_members' in membership
            assert 'can_pin_messages' in membership
            assert 'can_manage_members' in membership
    
    def test_memberships_have_correct_roles(self, owner_client, group_chat_with_roles, 
                                           admin_user, moderator_user, member_user, guest_user):
        """Проверка что роли участников корректны"""
        url = f"/api/v1/communications/chats/{group_chat_with_roles.id}/"
        response = owner_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        # Создаем словарь user_id -> role для проверки
        memberships_by_user = {m['user']: m for m in data['memberships']}
        
        assert memberships_by_user[admin_user.id]['role'] == 'admin'
        assert memberships_by_user[moderator_user.id]['role'] == 'moderator'
        assert memberships_by_user[member_user.id]['role'] == 'member'
        assert memberships_by_user[guest_user.id]['role'] == 'guest'
    
    def test_admin_permissions_in_membership(self, owner_client, group_chat_with_roles, admin_user):
        """Проверка что у админа правильные права"""
        url = f"/api/v1/communications/chats/{group_chat_with_roles.id}/"
        response = owner_client.get(url)
        
        data = response.json()
        admin_membership = next(m for m in data['memberships'] if m['user'] == admin_user.id)
        
        assert admin_membership['can_send_messages'] is True
        assert admin_membership['can_add_members'] is True
        assert admin_membership['can_remove_members'] is True
        assert admin_membership['can_pin_messages'] is True
        assert admin_membership['can_manage_members'] is True
    
    def test_moderator_permissions_in_membership(self, owner_client, group_chat_with_roles, moderator_user):
        """Проверка что у модератора правильные права"""
        url = f"/api/v1/communications/chats/{group_chat_with_roles.id}/"
        response = owner_client.get(url)
        
        data = response.json()
        mod_membership = next(m for m in data['memberships'] if m['user'] == moderator_user.id)
        
        assert mod_membership['can_send_messages'] is True
        assert mod_membership['can_add_members'] is False
        assert mod_membership['can_remove_members'] is False
        assert mod_membership['can_pin_messages'] is True
        assert mod_membership['can_manage_members'] is False
    
    def test_member_permissions_in_membership(self, owner_client, group_chat_with_roles, member_user):
        """Проверка что у обычного участника правильные права"""
        url = f"/api/v1/communications/chats/{group_chat_with_roles.id}/"
        response = owner_client.get(url)
        
        data = response.json()
        member_membership = next(m for m in data['memberships'] if m['user'] == member_user.id)
        
        assert member_membership['can_send_messages'] is True
        assert member_membership['can_add_members'] is False
        assert member_membership['can_remove_members'] is False
        assert member_membership['can_pin_messages'] is False
        assert member_membership['can_manage_members'] is False
    
    def test_guest_permissions_in_membership(self, owner_client, group_chat_with_roles, guest_user):
        """Проверка что у гостя правильные права (только чтение)"""
        url = f"/api/v1/communications/chats/{group_chat_with_roles.id}/"
        response = owner_client.get(url)
        
        data = response.json()
        guest_membership = next(m for m in data['memberships'] if m['user'] == guest_user.id)
        
        assert guest_membership['can_send_messages'] is False
        assert guest_membership['can_add_members'] is False
        assert guest_membership['can_remove_members'] is False
        assert guest_membership['can_pin_messages'] is False
        assert guest_membership['can_manage_members'] is False


# ==================== Тесты изменения ролей ====================


class TestChangeRole:
    """Тесты изменения ролей участников"""
    
    def test_owner_can_change_role_to_admin(self, owner_client, group_chat_with_roles, member_user):
        """Владелец может повысить участника до админа"""
        # 1. Изменяем роль через API
        change_role_url = f"/api/v1/communications/chats/{group_chat_with_roles.id}/change-role/"
        response = owner_client.post(change_role_url, {
            'user_id': member_user.id,
            'role': 'admin'
        })
        
        # 2. Проверяем успешный ответ
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data['ok'] is True
        assert data['membership']['role'] == 'admin'
        
        # 3. Получаем чат через API и проверяем что роль изменилась
        chat_url = f"/api/v1/communications/chats/{group_chat_with_roles.id}/"
        chat_response = owner_client.get(chat_url)
        
        assert chat_response.status_code == status.HTTP_200_OK
        chat_data = chat_response.json()
        
        # 4. Находим участника в memberships и проверяем его роль и права
        member_membership = next(
            (m for m in chat_data['memberships'] if m['user'] == member_user.id),
            None
        )
        
        assert member_membership is not None, "Участник не найден в memberships"
        assert member_membership['role'] == 'admin'
        assert member_membership['can_send_messages'] is True
        assert member_membership['can_add_members'] is True
        assert member_membership['can_remove_members'] is True
        assert member_membership['can_pin_messages'] is True
        assert member_membership['can_manage_members'] is True
    
    def test_owner_can_change_role_to_moderator(self, owner_client, group_chat_with_roles, member_user):
        """Владелец может назначить участника модератором"""
        # 1. Изменяем роль через API
        change_role_url = f"/api/v1/communications/chats/{group_chat_with_roles.id}/change-role/"
        response = owner_client.post(change_role_url, {
            'user_id': member_user.id,
            'role': 'moderator'
        })
        
        # 2. Проверяем успешный ответ
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data['membership']['role'] == 'moderator'
        
        # 3. Получаем чат через API и проверяем что роль изменилась
        chat_url = f"/api/v1/communications/chats/{group_chat_with_roles.id}/"
        chat_response = owner_client.get(chat_url)
        
        assert chat_response.status_code == status.HTTP_200_OK
        chat_data = chat_response.json()
        
        # 4. Проверяем роль и права через API
        # 1. Изменяем роль через API
        change_role_url = f"/api/v1/communications/chats/{group_chat_with_roles.id}/change-role/"
        response = owner_client.post(change_role_url, {
            'user_id': admin_user.id,
            'role': 'member'
        })
        
        # 2. Проверяем успешный ответ
        assert response.status_code == status.HTTP_200_OK
        
        # 3. Получаем чат через API и проверяем понижение прав
        chat_url = f"/api/v1/communications/chats/{group_chat_with_roles.id}/"
        chat_response = owner_client.get(chat_url)
        
        assert chat_response.status_code == status.HTTP_200_OK
        chat_data = chat_response.json()
        
        # 4. Проверяем что права понизились
        admin_membership = next(
            (m for m in chat_data['memberships'] if m['user'] == admin_user.id),
            None
        )
        
        assert admin_membership is not None
        assert admin_membership['role'] == 'member'
        assert admin_membership['can_send_messages'] is True
        assert admin_membership['can_add_members'] is False
        assert admin_membership['can_remove_members'] is False
        assert admin_membership['can_pin_messages'] is False
        assert admin_membership['can_manage_members']до обычного участника"""
        url = f"/api/v1/communications/chats/{group_chat_with_roles.id}/change-role/"
        response = owner_client.post(url, {
            'user_id': admin_user.id,
        # 1. Изменяем роль через API
        change_role_url = f"/api/v1/communications/chats/{group_chat_with_roles.id}/change-role/"
        response = owner_client.post(change_role_url, {
            'user_id': member_user.id,
            'role': 'guest'
        })
        
        # 2. Проверяем успешный ответ
        assert response.status_code == status.HTTP_200_OK
        
        # 3. Получаем чат через API и проверяем ограничение прав
        chat_url = f"/api/v1/communications/chats/{group_chat_with_roles.id}/"
        chat_response = owner_client.get(chat_url)
        
        assert chat_response.status_code == status.HTTP_200_OK
        chat_data = chat_response.json()
        
        # 4. Проверяем что участник теперь гость (только чтение)
        member_membership = next(
            (m for m in chat_data['memberships'] if m['user'] == member_user.id),
            None
        )
        
        assert member_membership is not None
        assert member_membership['role'] == 'guest'
        assert member_membership['can_send_messages'] is False
        assert member_membership['can_add_members'] is False
        assert member_membership['can_remove_members'] is False
        assert member_membership['can_pin_messages'] is False
        assert member_membership['can_manage_members'] is False
    
    def test_admin_cannot_change_roles(self, admin_client, group_chat_with_roles, member_user):
        """Админ НЕ может менять роли (только владелец)"""
        # 1. Пытаемся изменить роль через API
        change_role_url = f"/api/v1/communications/chats/{group_chat_with_roles.id}/change-role/"
        response = admin_client.post(change_role_url, {
            'user_id': member_user.id,
            'role': 'admin'
        })
        
        # 2. Проверяем что доступ запрещен
        assert response.status_code == status.HTTP_403_FORBIDDEN
        
        # 3. Получаем чат через API и проверяем что роль НЕ изменилась
        chat_url = f"/api/v1/communications/chats/{group_chat_with_roles.id}/"
        chat_response = admin_client.get(chat_url)
        
        assert chat_response.status_code == status.HTTP_200_OK
        chat_data = chat_response.json()
        
        # 4. Проверяем что роль осталась 'member'
        member_membership = next(
            (m for m in chat_data['memberships'] if m['user'] == member_user.id),
            None
        )
        
        assert member_membership is not None
        assert member_membership['role'] == 'member'
    
    def test_moderator_cannot_change_roles(self, moderator_client, group_chat_with_roles, member_user):
        """Модератор НЕ может менять роли"""
        # 1. Пытаемся изменить роль через API
        change_role_url = f"/api/v1/communications/chats/{group_chat_with_roles.id}/change-role/"
        response = moderator_client.post(change_role_url, {
            'user_id': member_user.id,
            'role': 'admin'
        })
        
        # 2. Проверяем что доступ запрещен
        assert response.status_code == status.HTTP_403_FORBIDDEN
        
        # 1. Пытаемся изменить роль через API
        change_role_url = f"/api/v1/communications/chats/{group_chat_with_roles.id}/change-role/"
        response = member_client.post(change_role_url, {
            'user_id': guest_user.id,
            'role': 'member'
        })
        
        # 2. Проверяем что доступ запрещен
        assert response.status_code == status.HTTP_403_FORBIDDEN
        
        # 3. Получаем чат через API и проверяем что роль НЕ изменилась
        chat_url = f"/api/v1/communications/chats/{group_chat_with_roles.id}/"
        chat_response = member_client.get(chat_url)
        
        assert chat_response.status_code == status.HTTP_200_OK
        chat_data = chat_response.json()
        
        # 4. Проверяем что роль осталась 'guest'
        guest_membership = next(
            (m for m in chat_data['memberships'] if m['user'] == guest_user.id),
            None
        )
        
        assert guest_membership is not None
        assert guest_membership['role'] == 'guest'
    
    def test_cannot_change_owner_role(self, owner_client, group_chat_with_roles, owner):
        """Нельзя изменить роль владельца чата"""
        url = f"/api/v1/communications/chats/{group_chat_with_roles.id}/change-role/"
        response = owner_client.post(url, {
            'user_id': owner.id,
            'role': 'member'
        })
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'owner' in response.json()['error'].lower()
    
    def test_invalid_role_rejected(self, owner_client, group_chat_with_roles, member_user):
        """Невалидная роль отклоняется"""
        url = f"/api/v1/communications/chats/{group_chat_with_roles.id}/change-role/"
        response = owner_client.post(url, {
            'user_id': member_user.id,
            'role': 'superadmin'  # Несуществующая роль
        })
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'invalid role' in response.json()['error'].lower()
    
    def test_missing_parameters_rejected(self, owner_client, group_chat_with_roles):
        """Запрос без обязательных параметров отклоняется"""
        url = f"/api/v1/communications/chats/{group_chat_with_roles.id}/change-role/"
        
        # Без user_id
        response = owner_client.post(url, {'role': 'admin'})
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        
        # Без role
        response = owner_client.post(url, {'user_id': 123})
        assert response.status_code == status.HTTP_400_BAD_REQUEST


# ==================== Тесты прав на отправку сообщений ====================


class TestSendMessagePermissions:
    """Тесты прав на отправку сообщений в зависимости от роли"""
    
    def test_owner_can_send_messages(self, owner_client, group_chat_with_roles):
        """Владелец может отправлять сообщения"""
        url = "/api/v1/communications/messages/"
        response = owner_client.post(url, {
            'chat': group_chat_with_roles.id,
            'content': 'Message from owner'
        })
        
        assert response.status_code == status.HTTP_201_CREATED
        assert Message.objects.filter(
            chat=group_chat_with_roles,
            content='Message from owner'
        ).exists()
    
    def test_admin_can_send_messages(self, admin_client, group_chat_with_roles):
        """Админ может отправлять сообщения"""
        url = "/api/v1/communications/messages/"
        response = admin_client.post(url, {
            'chat': group_chat_with_roles.id,
            'content': 'Message from admin'
        })
        
        assert response.status_code == status.HTTP_201_CREATED
    
    def test_moderator_can_send_messages(self, moderator_client, group_chat_with_roles):
        """Модератор может отправлять сообщения"""
        url = "/api/v1/communications/messages/"
        response = moderator_client.post(url, {
            'chat': group_chat_with_roles.id,
            'content': 'Message from moderator'
        })
        
        assert response.status_code == status.HTTP_201_CREATED
    
    def test_member_can_send_messages(self, member_client, group_chat_with_roles):
        """Обычный участник может отправлять сообщения"""
        url = "/api/v1/communications/messages/"
        response = member_client.post(url, {
            'chat': group_chat_with_roles.id,
            'content': 'Message from member'
        })
        
        assert response.status_code == status.HTTP_201_CREATED
    
    def test_guest_cannot_send_messages(self, guest_client, group_chat_with_roles):
        """Гость НЕ может отправлять сообщения"""
        url = "/api/v1/communications/messages/"
        response = guest_client.post(url, {
            'chat': group_chat_with_roles.id,
            'content': 'Message from guest'
        })
        
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert not Message.objects.filter(content='Message from guest').exists()
    
    def test_non_member_cannot_send_messages(self, regular_client, group_chat_with_roles):
        """Не-участник чата НЕ может отправлять сообщения"""
        url = "/api/v1/communications/messages/"
        response = regular_client.post(url, {
            'chat': group_chat_with_roles.id,
            'content': 'Message from outsider'
        })
        
        assert response.status_code == status.HTTP_403_FORBIDDEN


# ==================== Тесты прав на чтение сообщений ====================


class TestReadMessagePermissions:
    """Тесты прав на чтение сообщений"""
    
    @pytest.fixture
    def chat_with_messages(self, group_chat_with_roles, owner):
        """Чат с несколькими сообщениями"""
        Message.objects.create(
            chat=group_chat_with_roles,
            author=owner,
            content="Test message 1"
        )
        Message.objects.create(
            chat=group_chat_with_roles,
            author=owner,
            content="Test message 2"
        )
        return group_chat_with_roles
    
    def test_owner_can_read_messages(self, owner_client, chat_with_messages):
        """Владелец может читать сообщения"""
        url = f"/api/v1/communications/chats/{chat_with_messages.id}/messages/"
        response = owner_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data['results']) == 2
    
    def test_admin_can_read_messages(self, admin_client, chat_with_messages):
        """Админ может читать сообщения"""
        url = f"/api/v1/communications/chats/{chat_with_messages.id}/messages/"
        response = admin_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert len(response.json()['results']) == 2
    
    def test_moderator_can_read_messages(self, moderator_client, chat_with_messages):
        """Модератор может читать сообщения"""
        url = f"/api/v1/communications/chats/{chat_with_messages.id}/messages/"
        response = moderator_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert len(response.json()['results']) == 2
    
    def test_member_can_read_messages(self, member_client, chat_with_messages):
        """Обычный участник может читать сообщения"""
        url = f"/api/v1/communications/chats/{chat_with_messages.id}/messages/"
        response = member_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert len(response.json()['results']) == 2
    
    def test_guest_can_read_messages(self, guest_client, chat_with_messages):
        """Гость может читать сообщения (read-only доступ)"""
        url = f"/api/v1/communications/chats/{chat_with_messages.id}/messages/"
        response = guest_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert len(response.json()['results']) == 2
    
    def test_non_member_cannot_read_messages(self, regular_client, chat_with_messages):
        """Не-участник НЕ может читать сообщения"""
        url = f"/api/v1/communications/chats/{chat_with_messages.id}/messages/"
        response = regular_client.get(url)
        
        assert response.status_code == status.HTTP_403_FORBIDDEN


# ==================== Тесты прав на управление участниками ====================


class TestManageMembersPermissions:
    """Тесты прав на добавление и удаление участников"""
    
    def test_owner_can_add_members(self, owner_client, group_chat_with_roles, regular_user):
        """Владелец может добавлять участников"""
        url = f"/api/v1/communications/chats/{group_chat_with_roles.id}/add-member/"
        response = owner_client.post(url, {'user_id': regular_user.id})
        
        assert response.status_code == status.HTTP_200_OK
        assert group_chat_with_roles.participants.filter(id=regular_user.id).exists()
    
    def test_admin_can_add_members(self, admin_client, group_chat_with_roles, regular_user):
        """Админ может добавлять участников"""
        url = f"/api/v1/communications/chats/{group_chat_with_roles.id}/add-member/"
        response = admin_client.post(url, {'user_id': regular_user.id})
        
        assert response.status_code == status.HTTP_200_OK
        assert group_chat_with_roles.participants.filter(id=regular_user.id).exists()
    
    def test_moderator_cannot_add_members(self, moderator_client, group_chat_with_roles, regular_user):
        """Модератор НЕ может добавлять участников"""
        url = f"/api/v1/communications/chats/{group_chat_with_roles.id}/add-member/"
        response = moderator_client.post(url, {'user_id': regular_user.id})
        
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert not group_chat_with_roles.participants.filter(id=regular_user.id).exists()
    
    def test_member_cannot_add_members(self, member_client, group_chat_with_roles, regular_user):
        """Обычный участник НЕ может добавлять участников"""
        url = f"/api/v1/communications/chats/{group_chat_with_roles.id}/add-member/"
        response = member_client.post(url, {'user_id': regular_user.id})
        
        assert response.status_code == status.HTTP_403_FORBIDDEN
    
    def test_guest_cannot_add_members(self, guest_client, group_chat_with_roles, regular_user):
        """Гость НЕ может добавлять участников"""
        url = f"/api/v1/communications/chats/{group_chat_with_roles.id}/add-member/"
        response = guest_client.post(url, {'user_id': regular_user.id})
        
        assert response.status_code == status.HTTP_403_FORBIDDEN
    
    def test_owner_can_remove_members(self, owner_client, group_chat_with_roles, member_user):
        """Владелец может удалять участников"""
        url = f"/api/v1/communications/chats/{group_chat_with_roles.id}/remove-member/"
        response = owner_client.post(url, {'user_id': member_user.id})
        
        assert response.status_code == status.HTTP_200_OK
        assert not group_chat_with_roles.participants.filter(id=member_user.id).exists()
    
    def test_admin_can_remove_members(self, admin_client, group_chat_with_roles, member_user):
        """Админ может удалять участников"""
        url = f"/api/v1/communications/chats/{group_chat_with_roles.id}/remove-member/"
        response = admin_client.post(url, {'user_id': member_user.id})
        
        assert response.status_code == status.HTTP_200_OK
    
    def test_moderator_cannot_remove_members(self, moderator_client, group_chat_with_roles, member_user):
        """Модератор НЕ может удалять участников"""
        url = f"/api/v1/communications/chats/{group_chat_with_roles.id}/remove-member/"
        response = moderator_client.post(url, {'user_id': member_user.id})
        
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert group_chat_with_roles.participants.filter(id=member_user.id).exists()
    
    def test_cannot_remove_owner(self, admin_client, group_chat_with_roles, owner):
        """Нельзя удалить владельца чата"""
        url = f"/api/v1/communications/chats/{group_chat_with_roles.id}/remove-member/"
        response = admin_client.post(url, {'user_id': owner.id})
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'owner' in response.json()['error'].lower()


# ==================== Тесты прав на закрепление сообщений ====================


class TestPinMessagePermissions:
    """Тесты прав на закрепление сообщений"""
    
    @pytest.fixture
    def message_to_pin(self, group_chat_with_roles, owner):
        """Сообщение для закрепления"""
        return Message.objects.create(
            chat=group_chat_with_roles,
            author=owner,
            content="Message to pin"
        )
    
    def test_owner_can_pin_messages(self, owner_client, group_chat_with_roles, message_to_pin):
        """Владелец может закреплять сообщения"""
        url = f"/api/v1/communications/messages/{message_to_pin.id}/pin/"
        response = owner_client.post(url)
        
        assert response.status_code == status.HTTP_200_OK
        message_to_pin.refresh_from_db()
        assert message_to_pin.is_pinned is True
    
    def test_admin_can_pin_messages(self, admin_client, group_chat_with_roles, message_to_pin):
        """Админ может закреплять сообщения"""
        url = f"/api/v1/communications/messages/{message_to_pin.id}/pin/"
        response = admin_client.post(url)
        
        assert response.status_code == status.HTTP_200_OK
        message_to_pin.refresh_from_db()
        assert message_to_pin.is_pinned is True
    
    def test_moderator_can_pin_messages(self, moderator_client, group_chat_with_roles, message_to_pin):
        """Модератор может закреплять сообщения"""
        url = f"/api/v1/communications/messages/{message_to_pin.id}/pin/"
        response = moderator_client.post(url)
        
        assert response.status_code == status.HTTP_200_OK
        message_to_pin.refresh_from_db()
        assert message_to_pin.is_pinned is True
    
    def test_member_cannot_pin_messages(self, member_client, group_chat_with_roles, message_to_pin):
        """Обычный участник НЕ может закреплять сообщения"""
        url = f"/api/v1/communications/messages/{message_to_pin.id}/pin/"
        response = member_client.post(url)
        
        assert response.status_code == status.HTTP_403_FORBIDDEN
        message_to_pin.refresh_from_db()
        assert message_to_pin.is_pinned is False
    
    def test_guest_cannot_pin_messages(self, guest_client, group_chat_with_roles, message_to_pin):
        """Гость НЕ может закреплять сообщения"""
        url = f"/api/v1/communications/messages/{message_to_pin.id}/pin/"
        response = guest_client.post(url)
        
        assert response.status_code == status.HTTP_403_FORBIDDEN


# ==================== Тесты прав на реакции ====================


class TestReactionPermissions:
    """Тесты прав на отправку реакций"""
    
    @pytest.fixture
    def message_for_reaction(self, group_chat_with_roles, owner):
        """Сообщение для реакций"""
        return Message.objects.create(
            chat=group_chat_with_roles,
            author=owner,
            content="Message for reactions"
        )
    
    def test_owner_can_react(self, owner_client, message_for_reaction):
        """Владелец может ставить реакции"""
        url = f"/api/v1/communications/messages/{message_for_reaction.id}/react/"
        response = owner_client.post(url, {'emoji': '👍'})
        
        assert response.status_code == status.HTTP_200_OK
    
    def test_admin_can_react(self, admin_client, message_for_reaction):
        """Админ может ставить реакции"""
        url = f"/api/v1/communications/messages/{message_for_reaction.id}/react/"
        response = admin_client.post(url, {'emoji': '❤️'})
        
        assert response.status_code == status.HTTP_200_OK
    
    def test_moderator_can_react(self, moderator_client, message_for_reaction):
        """Модератор может ставить реакции"""
        url = f"/api/v1/communications/messages/{message_for_reaction.id}/react/"
        response = moderator_client.post(url, {'emoji': '😊'})
        
        assert response.status_code == status.HTTP_200_OK
    
    def test_member_can_react(self, member_client, message_for_reaction):
        """Обычный участник может ставить реакции"""
        url = f"/api/v1/communications/messages/{message_for_reaction.id}/react/"
        response = member_client.post(url, {'emoji': '🔥'})
        
        assert response.status_code == status.HTTP_200_OK
    
    def test_guest_can_react(self, guest_client, message_for_reaction):
        """Гость МОЖЕТ ставить реакции (даже если не может писать сообщения)"""
        url = f"/api/v1/communications/messages/{message_for_reaction.id}/react/"
        response = guest_client.post(url, {'emoji': '👀'})
        
        assert response.status_code == status.HTTP_200_OK
        
        # Проверяем, что реакция создана
        from communications.models import MessageReaction
        assert MessageReaction.objects.filter(
            message=message_for_reaction,
            emoji='👀'
        ).exists()
    
    def test_non_member_cannot_react(self, regular_client, message_for_reaction):
        """Не-участник чата НЕ может ставить реакции"""
        url = f"/api/v1/communications/messages/{message_for_reaction.id}/react/"
        response = regular_client.post(url, {'emoji': '😱'})
        
        # 404 потому что не-участник вообще не видит сообщение
        assert response.status_code == status.HTTP_404_NOT_FOUND


# ==================== Тесты создания чата с ролями ====================


class TestChatCreationWithRoles:
    """Тесты создания чата и автоматического назначения ролей"""
    
    def test_create_group_chat_creates_owner_as_participant(self, owner_client, owner):
        """При создании группового чата владелец автоматически добавляется в участники"""
        url = "/api/v1/communications/chats/"
        response = owner_client.post(url, {
            'type': 'group',
            'name': 'New Group Chat',
            'description': 'Test chat'
        })
        
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        
        chat = Chat.objects.get(id=data['id'])
        assert chat.participants.filter(id=owner.id).exists()
        assert chat.created_by == owner
    
    def test_add_member_creates_default_member_role(self, owner_client, owner, regular_user):
        """При добавлении участника в групповой чат создается membership с ролью 'member'"""
        # Создаем чат
        chat = Chat.objects.create(
            type='group',
            name='Test Chat',
            created_by=owner
        )
        chat.participants.add(owner)
        
        # Добавляем участника
        url = f"/api/v1/communications/chats/{chat.id}/add-member/"
        response = owner_client.post(url, {'user_id': regular_user.id})
        
        assert response.status_code == status.HTTP_200_OK
        
        # Проверяем что создался membership с ролью member
        membership = ChatMembership.objects.get(chat=chat, user=regular_user)
        assert membership.role == 'member'
        assert membership.can_send_messages is True
        assert membership.can_add_members is False
        assert membership.invited_by == owner


# ==================== Тесты edge cases ====================


class TestRoleEdgeCases:
    """Тесты граничных случаев и специфичных сценариев"""
    
    def test_changing_role_updates_permissions_immediately(self, owner_client, group_chat_with_roles, 
                                                          member_user, member_client):
        """Изменение роли немедленно обновляет права"""
        # Участник не может добавлять других участников
        url = f"/api/v1/communications/chats/{group_chat_with_roles.id}/add-member/"
        regular_user = User.objects.create_user(
            email="newuser@test.com",
            password="pass",
            phone_number="+79997777777",
            send_activation_email=False
        )
        
        response = member_client.post(url, {'user_id': regular_user.id})
        assert response.status_code == status.HTTP_403_FORBIDDEN
        
        # Повышаем до админа
        change_url = f"/api/v1/communications/chats/{group_chat_with_roles.id}/change-role/"
        owner_client.post(change_url, {
            'user_id': member_user.id,
            'role': 'admin'
        })
        
        # Теперь может добавлять участников
        response = member_client.post(url, {'user_id': regular_user.id})
        assert response.status_code == status.HTTP_200_OK
    
    def test_deactivated_membership_not_included(self, owner_client, group_chat_with_roles, member_user):
        """Деактивированные memberships не включаются в список"""
        # Деактивируем membership
        membership = ChatMembership.objects.get(chat=group_chat_with_roles, user=member_user)
        membership.is_active = False
        membership.save()
        
        # Получаем чат
        url = f"/api/v1/communications/chats/{group_chat_with_roles.id}/"
        response = owner_client.get(url)
        
        data = response.json()
        user_ids_in_memberships = [m['user'] for m in data['memberships']]
        
        # Деактивированный пользователь не должен быть в списке
        assert member_user.id not in user_ids_in_memberships
    
    def test_multiple_role_changes_in_sequence(self, owner_client, group_chat_with_roles, member_user):
        """Последовательные изменения ролей работают корректно"""
        url = f"/api/v1/communications/chats/{group_chat_with_roles.id}/change-role/"
        
        # member -> admin
        response = owner_client.post(url, {'user_id': member_user.id, 'role': 'admin'})
        assert response.status_code == status.HTTP_200_OK
        
        membership = ChatMembership.objects.get(chat=group_chat_with_roles, user=member_user)
        assert membership.role == 'admin'
        
        # admin -> moderator
        response = owner_client.post(url, {'user_id': member_user.id, 'role': 'moderator'})
        assert response.status_code == status.HTTP_200_OK
        
        membership.refresh_from_db()
        assert membership.role == 'moderator'
        
        # moderator -> guest
        response = owner_client.post(url, {'user_id': member_user.id, 'role': 'guest'})
        assert response.status_code == status.HTTP_200_OK
        
        membership.refresh_from_db()
        assert membership.role == 'guest'
        assert membership.can_send_messages is False
