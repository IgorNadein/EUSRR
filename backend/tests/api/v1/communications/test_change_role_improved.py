"""
Тесты для изменения ролей участников чата

Проверяет:
- Изменение ролей через API
- Проверку изменений через повторный GET запрос
- Права доступа на изменение ролей
"""

import pytest
from communications.models import Chat, ChatMembership, Message
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APIClient

User = get_user_model()
pytestmark = pytest.mark.django_db


class TestChangeRoleImproved:
    """Улучшенные тесты изменения ролей с проверкой через GET запрос"""
    
    @pytest.fixture
    def owner(self, db):
        return User.objects.create_user(
            email="owner_test@test.com",
            password="testpass123",
            first_name="Owner",
            last_name="Test",
            phone_number="+79001234567",
            send_activation_email=False,
        )
    
    @pytest.fixture
    def member_user(self, db):
        return User.objects.create_user(
            email="member_test@test.com",
            password="testpass123",
            first_name="Member",
            last_name="Test",
            phone_number="+79001234568",
            send_activation_email=False,
        )
    
    @pytest.fixture
    def test_chat(self, owner, member_user):
        chat = Chat.objects.create(
            type="group",
            name="Test Chat",
            created_by=owner
        )
        chat.participants.add(owner, member_user)
        
        ChatMembership.objects.create(
            chat=chat,
            user=member_user,
            role='member',
            invited_by=owner
        )
        
        return chat
    
    @pytest.fixture
    def owner_client(self, owner):
        client = APIClient()
        client.force_authenticate(user=owner)
        return client
    
    def test_change_role_and_verify_via_api(self, owner_client, test_chat, member_user):
        """
        Тест: изменить роль, дождаться ответа, проверить через GET
        """
        # Шаг 1: Изменяем роль через POST
        change_url = f"/api/v1/communications/chats/{test_chat.id}/change-role/"
        response = owner_client.post(change_url, {
            'user_id': member_user.id,
            'role': 'admin'
        })
        
        # Шаг 2: Проверяем успешный ответ
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data['ok'] is True
        assert data['membership']['role'] == 'admin'
        
        # Шаг 3: Получаем чат через GET и проверяем роль
        chat_url = f"/api/v1/communications/chats/{test_chat.id}/"
        get_response = owner_client.get(chat_url)
        
        assert get_response.status_code == status.HTTP_200_OK
        chat_data = get_response.json()
        
        # Шаг 4: Находим участника и проверяем роль
        member_membership = next(
            (m for m in chat_data['memberships'] if m['user'] == member_user.id),
            None
        )
        
        assert member_membership is not None, "Участник не найден"
        assert member_membership['role'] == 'admin'
        assert member_membership['can_send_messages'] is True
        assert member_membership['can_add_members'] is True
    
    def test_member_to_guest_role_change(self, owner_client, test_chat, member_user):
        """
        Тест: изменение member → guest с проверкой через API
        """
        # Шаг 1: Изменяем роль
        change_url = f"/api/v1/communications/chats/{test_chat.id}/change-role/"
        response = owner_client.post(change_url, {
            'user_id': member_user.id,
            'role': 'guest'
        })
        
        # Шаг 2: Проверяем ответ
        assert response.status_code == status.HTTP_200_OK
        
        # Шаг 3: Проверяем через GET
        chat_url = f"/api/v1/communications/chats/{test_chat.id}/"
        get_response = owner_client.get(chat_url)
        
        chat_data = get_response.json()
        member_membership = next(
            (m for m in chat_data['memberships'] if m['user'] == member_user.id),
            None
        )
        
        # Шаг 4: Проверяем что стал гостем (только чтение)
        assert member_membership['role'] == 'guest'
        assert member_membership['can_send_messages'] is False
        assert member_membership['can_add_members'] is False
        assert member_membership['can_remove_members'] is False
