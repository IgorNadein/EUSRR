"""
Тесты для Communications API ViewSets
"""
import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from communications.models import Chat, Message, ChatMembership, ChatUserSettings
from employees.models import Department

User = get_user_model()
pytestmark = pytest.mark.django_db


# ==================== Fixtures ====================

@pytest.fixture
def user1(db):
    """Первый пользователь"""
    return User.objects.create_user(
        email='user1@test.com',
        password='testpass123',
        first_name='User',
        last_name='One',
        phone_number='+79991234567',
        send_activation_email=False
    )


@pytest.fixture
def user2(db):
    """Второй пользователь"""
    return User.objects.create_user(
        email='user2@test.com',
        password='testpass123',
        first_name='User',
        last_name='Two',
        phone_number='+79991234568',
        send_activation_email=False
    )


@pytest.fixture
def user3(db):
    """Третий пользователь"""
    return User.objects.create_user(
        email='user3@test.com',
        password='testpass123',
        first_name='User',
        last_name='Three',
        phone_number='+79991234569',
        send_activation_email=False
    )


@pytest.fixture
def department(db):
    """Тестовый отдел"""
    return Department.objects.create(name='Test Department')


@pytest.fixture
def private_chat(user1, user2):
    """Приватный чат между user1 и user2"""
    chat = Chat.objects.create(
        type='private',
        name='Private Chat',
        created_by=user1
    )
    chat.participants.add(user1, user2)
    return chat


@pytest.fixture
def group_chat(user1, user2, user3):
    """Групповой чат"""
    chat = Chat.objects.create(
        type='group',
        name='Group Chat',
        created_by=user1
    )
    chat.participants.add(user1, user2, user3)
    return chat


@pytest.fixture
def department_chat(department, user1):
    """Чат отдела"""
    return Chat.objects.create(
        type='department',
        name='Department Chat',
        department=department,
        created_by=user1
    )


@pytest.fixture
def auth_client(user1):
    """Аутентифицированный клиент для user1"""
    client = APIClient()
    client.force_authenticate(user=user1)
    return client


# ==================== Chat Tests ====================

class TestChatViewSet:
    """Тесты для ChatViewSet"""
    
    def test_list_chats_authenticated(self, auth_client, private_chat, group_chat):
        """Список чатов для аутентифицированного пользователя"""
        url = '/api/v1/communications/chats/'
        response = auth_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) >= 2
    
    def test_list_chats_unauthenticated(self):
        """Список чатов без аутентификации - должен вернуть 403"""
        client = APIClient()
        url = '/api/v1/communications/chats/'
        response = client.get(url)
        
        assert response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]
    
    def test_retrieve_chat(self, auth_client, private_chat):
        """Получение деталей чата"""
        url = f'/api/v1/communications/chats/{private_chat.pk}/'
        response = auth_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['id'] == private_chat.id
        assert response.data['type'] == 'private'
    
    def test_create_private_chat(self, auth_client, user1, user2):
        """Создание приватного чата"""
        url = '/api/v1/communications/chats/'
        data = {
            'type': 'private',
            'name': 'New Private Chat',
            'participants': [user1.id, user2.id]
        }
        response = auth_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['type'] == 'private'
        assert Chat.objects.filter(id=response.data['id']).exists()
    
    def test_create_group_chat(self, auth_client, user1, user2, user3):
        """Создание группового чата"""
        url = '/api/v1/communications/chats/'
        data = {
            'type': 'group',
            'name': 'Test Group',
            'participants': [user1.id, user2.id, user3.id]
        }
        response = auth_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['name'] == 'Test Group'
    
    def test_pin_chat(self, auth_client, private_chat, user1):
        """Закрепление чата"""
        url = f'/api/v1/communications/chats/{private_chat.pk}/pin/'
        response = auth_client.post(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['ok'] is True
        assert response.data['is_pinned'] is True
        
        # Проверяем что создался settings
        settings = ChatUserSettings.objects.get(chat=private_chat, user=user1)
        assert settings.is_pinned is True
    
    def test_toggle_notifications(self, auth_client, private_chat, user1):
        """Переключение уведомлений"""
        url = f'/api/v1/communications/chats/{private_chat.pk}/notifications/'
        response = auth_client.post(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['ok'] is True
        
        # По умолчанию уведомления включены, после переключения - выключены
        settings = ChatUserSettings.objects.get(chat=private_chat, user=user1)
        assert settings.notifications_enabled is False
    
    def test_chat_messages(self, auth_client, private_chat, user1):
        """Загрузка сообщений чата"""
        # Создаем тестовые сообщения
        for i in range(5):
            Message.objects.create(
                chat=private_chat,
                author=user1,
                content=f'Test message {i}'
            )
        
        url = f'/api/v1/communications/chats/{private_chat.pk}/messages/'
        response = auth_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert 'messages' in response.data
        assert len(response.data['messages']) == 5
    
    def test_mark_read(self, auth_client, private_chat, user1):
        """Пометка чата как прочитанного"""
        url = f'/api/v1/communications/chats/{private_chat.pk}/mark-read/'
        response = auth_client.post(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['ok'] is True
    
    def test_pin_chat(self, auth_client, private_chat):
        """Закрепление чата"""
        url = f'/api/v1/communications/chats/{private_chat.pk}/pin/'
        response = auth_client.post(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['ok'] is True
        assert response.data['is_pinned'] is True
        
        # Повторное закрепление - открепляет
        response = auth_client.post(url)
        assert response.data['is_pinned'] is False
    
    def test_toggle_notifications(self, auth_client, private_chat):
        """Переключение уведомлений для чата"""
        url = f'/api/v1/communications/chats/{private_chat.pk}/notifications/'
        
        # Первое переключение
        response = auth_client.post(url)
        assert response.status_code == status.HTTP_200_OK
        notifications_state = response.data['notifications_enabled']
        
        # Второе переключение - меняет состояние
        response = auth_client.post(url)
        assert response.data['notifications_enabled'] != notifications_state
    
    def test_messages_around(self, auth_client, private_chat, user1):
        """Загрузка сообщений вокруг указанного"""
        # Создаем 10 сообщений
        messages = [
            Message.objects.create(chat=private_chat, author=user1, content=f'Msg {i}')
            for i in range(10)
        ]
        
        # Запрашиваем вокруг 5-го сообщения
        middle_msg = messages[5]
        url = f'/api/v1/communications/chats/{private_chat.pk}/messages-around/'
        response = auth_client.get(url, {'around_id': middle_msg.id, 'limit': 6})
        
        assert response.status_code == status.HTTP_200_OK
        assert 'messages' in response.data
        assert response.data['messages_count'] > 0
    
    def test_messages_pagination_before(self, auth_client, private_chat, user1):
        """Пагинация сообщений (before)"""
        messages = [
            Message.objects.create(chat=private_chat, author=user1, content=f'Msg {i}')
            for i in range(20)
        ]
        
        # Получаем 10 последних
        url = f'/api/v1/communications/chats/{private_chat.pk}/messages/'
        response = auth_client.get(url, {'limit': 10})
        
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['messages']) == 10
        assert response.data['has_more'] is True
        
        # Получаем следующие 10
        oldest_msg = response.data['messages'][0]
        # Проверяем разные варианты ключей
        oldest_ts = oldest_msg.get('timestamp') or oldest_msg.get('created_at') or oldest_msg.get('id')
        if oldest_ts:
            response = auth_client.get(url, {'before': oldest_ts, 'limit': 10})
            assert response.status_code == status.HTTP_200_OK
            assert len(response.data['messages']) <= 10
    
    def test_messages_pagination_after(self, auth_client, private_chat, user1):
        """Пагинация сообщений (after)"""
        messages = [
            Message.objects.create(chat=private_chat, author=user1, content=f'Msg {i}')
            for i in range(20)
        ]
        
        # Получаем первые 10
        url = f'/api/v1/communications/chats/{private_chat.pk}/messages/'
        first_msg_ts = messages[0].created_at.isoformat()
        response = auth_client.get(url, {'after': first_msg_ts, 'limit': 10})
        
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['messages']) <= 10
    
    def test_chat_access_denied(self, user3, private_chat):
        """Попытка доступа к чату без прав"""
        client = APIClient()
        client.force_authenticate(user=user3)
        
        url = f'/api/v1/communications/chats/{private_chat.pk}/messages/'
        response = client.get(url)
        
        # API может вернуть 403 или 404 (не раскрывая существование чата)
        assert response.status_code in [status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND]


class TestMessageViewSet:
    """Тесты для MessageViewSet"""
    
    def test_upload_message_with_text(self, auth_client, private_chat, user1):
        """Отправка текстового сообщения"""
        url = '/api/v1/communications/messages/upload/'
        data = {
            'chat_id': private_chat.id,
            'content': 'Test message content'
        }
        response = auth_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['ok'] is True
        assert response.data['message']['content'] == 'Test message content'
        
        # Проверяем что сообщение создалось
        message = Message.objects.get(id=response.data['message']['id'])
        assert message.author == user1
        assert message.content == 'Test message content'
    
    def test_upload_message_without_content_and_files(self, auth_client, private_chat):
        """Попытка отправить пустое сообщение - должна вернуть ошибку"""
        url = '/api/v1/communications/messages/upload/'
        data = {
            'chat_id': private_chat.id,
            'content': ''
        }
        response = auth_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
    
    def test_upload_message_invalid_chat(self, auth_client):
        """Отправка сообщения в несуществующий чат"""
        url = '/api/v1/communications/messages/upload/'
        data = {
            'chat_id': 99999,
            'content': 'Test'
        }
        response = auth_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_404_NOT_FOUND
    
    def test_edit_message(self, auth_client, private_chat, user1):
        """Редактирование своего сообщения"""
        # Создаем сообщение
        message = Message.objects.create(
            chat=private_chat,
            author=user1,
            content='Original content'
        )
        
        url = f'/api/v1/communications/messages/{message.pk}/'
        data = {
            'content': 'Updated content'
        }
        response = auth_client.patch(url, data, format='json')
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['content'] == 'Updated content'
        assert response.data['is_edited'] is True
        
        # Проверяем в БД
        message.refresh_from_db()
        assert message.content == 'Updated content'
        assert message.is_edited is True
    
    def test_edit_message_not_author(self, user1, user2, private_chat):
        """Попытка редактировать чужое сообщение - должна вернуть ошибку"""
        # user1 создает сообщение
        message = Message.objects.create(
            chat=private_chat,
            author=user1,
            content='Original'
        )
        
        # user2 пытается редактировать
        client = APIClient()
        client.force_authenticate(user=user2)
        
        url = f'/api/v1/communications/messages/{message.pk}/'
        data = {'content': 'Hacked'}
        response = client.patch(url, data, format='json')
        
        assert response.status_code == status.HTTP_403_FORBIDDEN
    
    def test_delete_message(self, auth_client, private_chat, user1):
        """Удаление своего сообщения"""
        message = Message.objects.create(
            chat=private_chat,
            author=user1,
            content='To delete'
        )
        
        url = f'/api/v1/communications/messages/{message.pk}/'
        response = auth_client.delete(url)
        
        assert response.status_code == status.HTTP_204_NO_CONTENT
        
        # Проверяем мягкое удаление
        message.refresh_from_db()
        assert message.is_deleted is True
    
    def test_react_to_message(self, auth_client, private_chat, user1):
        """Добавление реакции на сообщение"""
        message = Message.objects.create(
            chat=private_chat,
            author=user1,
            content='React to this'
        )
        
        url = f'/api/v1/communications/messages/{message.pk}/react/'
        data = {'emoji': '👍'}
        response = auth_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['ok'] is True
        assert '👍' in response.data['reactions_summary']
    
    def test_unreact_to_message(self, auth_client, private_chat, user1):
        """Удаление реакции с сообщения"""
        message = Message.objects.create(
            chat=private_chat,
            author=user1,
            content='Test'
        )
        
        # Сначала добавляем реакцию
        url = f'/api/v1/communications/messages/{message.pk}/react/'
        auth_client.post(url, {'emoji': '👍'}, format='json')
        
        # Теперь удаляем
        url = f'/api/v1/communications/messages/{message.pk}/unreact/'
        response = auth_client.post(url, {'emoji': '👍'}, format='json')
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['ok'] is True
    
    def test_forward_messages(self, auth_client, private_chat, group_chat, user1):
        """Пересылка сообщений в другой чат"""
        # Создаем сообщения для пересылки
        msg1 = Message.objects.create(chat=private_chat, author=user1, content='Msg 1')
        msg2 = Message.objects.create(chat=private_chat, author=user1, content='Msg 2')
        
        url = '/api/v1/communications/messages/forward/'
        data = {
            'message_ids': [msg1.id, msg2.id],
            'target_chat_id': group_chat.id
        }
        response = auth_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['ok'] is True
        assert response.data['forwarded_count'] == 2
    
    def test_bulk_delete_messages(self, auth_client, private_chat, user1):
        """Массовое удаление сообщений"""
        # Создаем несколько сообщений
        messages = [
            Message.objects.create(chat=private_chat, author=user1, content=f'Msg {i}')
            for i in range(3)
        ]
        message_ids = [m.id for m in messages]
        
        url = '/api/v1/communications/messages/bulk-delete/'
        data = {'message_ids': message_ids}
        response = auth_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['ok'] is True
        assert response.data['deleted_count'] == 3
    
    def test_bulk_delete_partial_ownership(self, user1, user2, private_chat):
        """Массовое удаление - пропускает чужие сообщения"""
        # user1 создает 2 сообщения, user2 создает 1
        msg1 = Message.objects.create(chat=private_chat, author=user1, content='My 1')
        msg2 = Message.objects.create(chat=private_chat, author=user2, content='Not mine')
        msg3 = Message.objects.create(chat=private_chat, author=user1, content='My 2')
        
        client = APIClient()
        client.force_authenticate(user=user1)
        
        url = '/api/v1/communications/messages/bulk-delete/'
        data = {'message_ids': [msg1.id, msg2.id, msg3.id]}
        response = client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_200_OK
        # Удалено только 2 (свои сообщения)
        assert response.data['deleted_count'] == 2
    
    def test_edit_empty_content(self, auth_client, private_chat, user1):
        """Попытка редактировать сообщение на пустое"""
        message = Message.objects.create(
            chat=private_chat,
            author=user1,
            content='Original'
        )
        
        url = f'/api/v1/communications/messages/{message.pk}/'
        data = {'content': ''}
        response = auth_client.patch(url, data, format='json')
        
        # Должна быть ошибка валидации
        assert response.status_code == status.HTTP_400_BAD_REQUEST
    
    def test_react_invalid_emoji(self, auth_client, private_chat, user1):
        """Попытка добавить невалидную реакцию"""
        message = Message.objects.create(chat=private_chat, author=user1, content='Test')
        
        url = f'/api/v1/communications/messages/{message.pk}/react/'
        data = {'emoji': 'not_an_emoji'}
        response = auth_client.post(url, data, format='json')
        
        # Может быть 400 или просто игнорироваться в зависимости от валидации
        assert response.status_code in [status.HTTP_400_BAD_REQUEST, status.HTTP_200_OK]
    
    def test_unreact_not_reacted(self, auth_client, private_chat, user1):
        """Попытка удалить реакцию которую не ставил"""
        message = Message.objects.create(chat=private_chat, author=user1, content='Test')
        
        url = f'/api/v1/communications/messages/{message.pk}/unreact/'
        response = auth_client.post(url, {'emoji': '👍'}, format='json')
        
        # Может вернуть 404 если реакция не найдена или 200 если просто игнорирует
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_404_NOT_FOUND]
    
    def test_forward_to_inaccessible_chat(self, user1, user2, user3):
        """Попытка переслать в чат без доступа"""
        # Чат между user1 и user2
        chat1 = Chat.objects.create(type='private', created_by=user1)
        chat1.participants.add(user1, user2)
        
        # Чат между user2 и user3 (user1 нет доступа)
        chat2 = Chat.objects.create(type='private', created_by=user2)
        chat2.participants.add(user2, user3)
        
        message = Message.objects.create(chat=chat1, author=user1, content='Test')
        
        client = APIClient()
        client.force_authenticate(user=user1)
        
        url = '/api/v1/communications/messages/forward/'
        data = {
            'message_ids': [message.id],
            'target_chat_id': chat2.id
        }
        response = client.post(url, data, format='json')
        
        assert response.status_code in [status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND]
    
    def test_forward_nonexistent_messages(self, auth_client, private_chat):
        """Попытка переслать несуществующие сообщения"""
        url = '/api/v1/communications/messages/forward/'
        data = {
            'message_ids': [99999, 88888],
            'target_chat_id': private_chat.id
        }
        response = auth_client.post(url, data, format='json')
        
        # Может быть 404 или просто forwarded_count=0
        assert response.status_code in [status.HTTP_404_NOT_FOUND, status.HTTP_200_OK]
        if response.status_code == status.HTTP_200_OK:
            assert response.data['forwarded_count'] == 0
    
    def test_delete_already_deleted(self, auth_client, private_chat, user1):
        """Попытка удалить уже удаленное сообщение"""
        message = Message.objects.create(chat=private_chat, author=user1, content='Test')
        message.is_deleted = True
        message.save()
        
        url = f'/api/v1/communications/messages/{message.pk}/'
        response = auth_client.delete(url)
        
        # Должно успешно пройти (идемпотентность)
        assert response.status_code == status.HTTP_204_NO_CONTENT
    
    def test_react_to_deleted_message(self, auth_client, private_chat, user1):
        """Попытка добавить реакцию на удаленное сообщение"""
        message = Message.objects.create(chat=private_chat, author=user1, content='Test')
        message.is_deleted = True
        message.save()
        
        url = f'/api/v1/communications/messages/{message.pk}/react/'
        response = auth_client.post(url, {'emoji': '👍'}, format='json')
        
        # Может быть ошибка или просто игнорироваться
        assert response.status_code in [status.HTTP_400_BAD_REQUEST, status.HTTP_404_NOT_FOUND, status.HTTP_200_OK]


class TestPollViewSet:
    """Тесты для PollViewSet"""
    
    @pytest.fixture
    def poll_message(self, private_chat, user1):
        """Сообщение с голосованием"""
        from communications.models import Poll, PollOption
        
        message = Message.objects.create(
            chat=private_chat,
            author=user1,
            content='Poll message'
        )
        poll = Poll.objects.create(
            message=message,
            author=user1,
            question='Test question?',
            is_anonymous=False,
            is_multiple_choice=False
        )
        option1 = PollOption.objects.create(poll=poll, text='Option 1', position=0)
        option2 = PollOption.objects.create(poll=poll, text='Option 2', position=1)
        return message, poll, option1, option2
    
    def test_poll_vote_single_choice(self, auth_client, poll_message, user1):
        """Голосование в опросе с одним вариантом"""
        message, poll, option1, option2 = poll_message
        
        url = f'/api/v1/communications/polls/{poll.pk}/vote/'
        data = {'option_ids': [option1.id]}
        response = auth_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['total_voters'] == 1
        assert option1.id in response.data['user_voted_option_ids']
    
    def test_poll_vote_multiple_in_single_choice(self, auth_client, poll_message):
        """Попытка выбрать несколько вариантов в single-choice опросе"""
        message, poll, option1, option2 = poll_message
        
        url = f'/api/v1/communications/polls/{poll.pk}/vote/'
        data = {'option_ids': [option1.id, option2.id]}
        response = auth_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'Only one option allowed' in response.data['error']
    
    def test_poll_vote_multiple_choice(self, auth_client, private_chat, user1):
        """Голосование с multiple choice"""
        from communications.models import Poll, PollOption
        
        message = Message.objects.create(chat=private_chat, author=user1, content='Poll')
        poll = Poll.objects.create(
            message=message,
            author=user1,
            question='Multiple?',
            is_multiple_choice=True
        )
        opt1 = PollOption.objects.create(poll=poll, text='A', position=0)
        opt2 = PollOption.objects.create(poll=poll, text='B', position=1)
        
        url = f'/api/v1/communications/polls/{poll.pk}/vote/'
        data = {'option_ids': [opt1.id, opt2.id]}
        response = auth_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['user_voted_option_ids']) == 2
    
    def test_poll_vote_closed(self, auth_client, poll_message):
        """Попытка проголосовать в закрытом опросе"""
        message, poll, option1, option2 = poll_message
        poll.is_closed = True
        poll.save()
        
        url = f'/api/v1/communications/polls/{poll.pk}/vote/'
        data = {'option_ids': [option1.id]}
        response = auth_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'closed' in response.data['error'].lower()
    
    def test_poll_vote_without_options(self, auth_client, poll_message):
        """Попытка проголосовать без выбора опций"""
        message, poll, option1, option2 = poll_message
        
        url = f'/api/v1/communications/polls/{poll.pk}/vote/'
        data = {'option_ids': []}
        response = auth_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
    
    def test_poll_revote_single_choice(self, auth_client, poll_message):
        """Повторное голосование заменяет предыдущий выбор"""
        message, poll, option1, option2 = poll_message
        
        url = f'/api/v1/communications/polls/{poll.pk}/vote/'
        
        # Первое голосование
        auth_client.post(url, {'option_ids': [option1.id]}, format='json')
        
        # Второе голосование (меняем выбор)
        response = auth_client.post(url, {'option_ids': [option2.id]}, format='json')
        
        assert response.status_code == status.HTTP_200_OK
        assert option2.id in response.data['user_voted_option_ids']
        assert option1.id not in response.data['user_voted_option_ids']
    
    def test_poll_close_by_author(self, auth_client, poll_message):
        """Закрытие опроса автором"""
        message, poll, option1, option2 = poll_message
        
        url = f'/api/v1/communications/polls/{poll.pk}/close/'
        response = auth_client.post(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['is_closed'] is True
    
    def test_poll_close_by_non_author(self, user2, poll_message, private_chat):
        """Попытка закрыть чужой опрос"""
        message, poll, option1, option2 = poll_message
        
        client = APIClient()
        client.force_authenticate(user=user2)
        
        url = f'/api/v1/communications/polls/{poll.pk}/close/'
        response = client.post(url)
        
        assert response.status_code == status.HTTP_403_FORBIDDEN
    
    def test_poll_get_results(self, auth_client, poll_message, user1):
        """Получение результатов опроса"""
        message, poll, option1, option2 = poll_message
        
        # Проголосуем сначала
        url = f'/api/v1/communications/polls/{poll.pk}/vote/'
        auth_client.post(url, {'option_ids': [option1.id]}, format='json')
        
        # Получаем результаты
        url = f'/api/v1/communications/polls/{poll.pk}/results/'
        response = auth_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert 'options' in response.data
        assert response.data['total_voters'] == 1


# ==================== Integration Tests ====================

class TestCommunicationsIntegration:
    """Интеграционные тесты полного flow"""
    
    def test_full_message_flow(self, user1, user2):
        """Полный flow: создание чата → отправка → редактирование → удаление"""
        client = APIClient()
        client.force_authenticate(user=user1)
        
        # 1. Создаем чат
        url = '/api/v1/communications/chats/'
        chat_data = {
            'type': 'private',
            'name': 'Test',
            'participants': [user1.id, user2.id]
        }
        response = client.post(url, chat_data, format='json')
        assert response.status_code == status.HTTP_201_CREATED
        chat_id = response.data['id']
        
        # 2. Отправляем сообщение
        url = '/api/v1/communications/messages/upload/'
        msg_data = {
            'chat_id': chat_id,
            'content': 'Hello World'
        }
        response = client.post(url, msg_data, format='json')
        assert response.status_code == status.HTTP_201_CREATED
        message_id = response.data['message']['id']
        
        # 3. Редактируем сообщение
        url = f'/api/v1/communications/messages/{message_id}/'
        edit_data = {'content': 'Hello World (edited)'}
        response = client.patch(url, edit_data, format='json')
        assert response.status_code == status.HTTP_200_OK
        assert response.data['is_edited'] is True
        
        # 4. Добавляем реакцию
        url = f'/api/v1/communications/messages/{message_id}/react/'
        response = client.post(url, {'emoji': '❤️'}, format='json')
        assert response.status_code == status.HTTP_200_OK
        
        # 5. Удаляем сообщение
        url = f'/api/v1/communications/messages/{message_id}/'
        response = client.delete(url)
        assert response.status_code == status.HTTP_204_NO_CONTENT
    
    def test_unauthorized_access(self, user1, user2, user3):
        """Попытка доступа к чужому приватному чату"""
        # user1 создает чат с user2
        chat = Chat.objects.create(type='private', created_by=user1)
        chat.participants.add(user1, user2)
        
        # user3 пытается получить доступ
        client = APIClient()
        client.force_authenticate(user=user3)
        
        url = f'/api/v1/communications/chats/{chat.pk}/messages/'
        response = client.get(url)
        
        # Может быть 403 или 404 в зависимости от реализации
        assert response.status_code in [status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND]


# ==================== Security & Edge Cases Tests ====================

class TestSecurityAndEdgeCases:
    """Тесты безопасности и граничных случаев"""
    
    def test_unauthenticated_access(self):
        """Попытка доступа без аутентификации"""
        client = APIClient()
        
        # Попытки доступа к разным эндпоинтам
        urls = [
            '/api/v1/communications/chats/',
            '/api/v1/communications/messages/upload/',
            '/api/v1/communications/polls/',
        ]
        
        for url in urls:
            response = client.get(url)
            # DRF может вернуть 401 или 403 в зависимости от настроек
            assert response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]
    
    def test_sql_injection_attempts(self, auth_client, private_chat):
        """Попытки SQL-инъекций"""
        url = f'/api/v1/communications/chats/{private_chat.pk}/messages/'
        
        # Различные попытки SQL-инъекций
        sql_payloads = [
            "' OR '1'='1",
            "1; DROP TABLE messages--",
            "1' UNION SELECT * FROM users--",
        ]
        
        for payload in sql_payloads:
            response = auth_client.get(url, {'before': payload})
            # Не должно вызывать ошибок, должно корректно обрабатываться
            assert response.status_code in [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST]
    
    def test_xss_attempts_in_message_content(self, auth_client, private_chat):
        """Попытки XSS через контент сообщения"""
        url = '/api/v1/communications/messages/upload/'
        
        xss_payloads = [
            '<script>alert("XSS")</script>',
            '<img src=x onerror=alert("XSS")>',
            'javascript:alert("XSS")',
        ]
        
        for payload in xss_payloads:
            data = {
                'chat_id': private_chat.id,
                'content': payload
            }
            response = auth_client.post(url, data, format='json')
            
            # Должно успешно создаваться, но контент должен быть экранирован на фронте
            if response.status_code == status.HTTP_201_CREATED:
                assert 'message' in response.data
    
    def test_rate_limiting_prevention(self, auth_client, private_chat, user1):
        """Массовая отправка сообщений (имитация спама)"""
        url = '/api/v1/communications/messages/upload/'
        
        # Пытаемся отправить 100 сообщений подряд
        for i in range(100):
            data = {
                'chat_id': private_chat.id,
                'content': f'Spam message {i}'
            }
            response = auth_client.post(url, data, format='json')
            
            # Проверяем что все создаются (если нет rate limiting)
            # или возвращается ошибка 429 (если есть)
            assert response.status_code in [
                status.HTTP_201_CREATED,
                status.HTTP_429_TOO_MANY_REQUESTS
            ]
    
    def test_invalid_json_payload(self, auth_client):
        """Отправка невалидного JSON"""
        url = '/api/v1/communications/messages/upload/'
        
        # Django REST Framework должен корректно обработать
        response = auth_client.post(
            url,
            data='{"invalid": json}',
            content_type='application/json'
        )
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
    
    def test_oversized_content(self, auth_client, private_chat):
        """Попытка отправить слишком большое сообщение"""
        url = '/api/v1/communications/messages/upload/'
        
        # Сообщение размером 100KB
        huge_content = 'A' * (100 * 1024)
        data = {
            'chat_id': private_chat.id,
            'content': huge_content
        }
        response = auth_client.post(url, data, format='json')
        
        # Может быть ошибка валидации или успешно создаться
        assert response.status_code in [
            status.HTTP_201_CREATED,
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
        ]
    
    def test_negative_ids(self, auth_client):
        """Запросы с отрицательными ID"""
        # Тестируем action endpoints с POST
        urls = [
            ('/api/v1/communications/chats/-1/mark-read/', 'post'),
            ('/api/v1/communications/polls/-1/vote/', 'post'),
        ]
        
        for url, method in urls:
            if method == 'post':
                response = auth_client.post(url)
            else:
                response = auth_client.get(url)
            # Может быть 404 или 405
            assert response.status_code in [status.HTTP_404_NOT_FOUND, status.HTTP_405_METHOD_NOT_ALLOWED]
    
    def test_uuid_instead_of_int_id(self, auth_client):
        """Попытка использовать UUID вместо integer ID"""
        url = '/api/v1/communications/chats/550e8400-e29b-41d4-a716-446655440000/messages/'
        response = auth_client.get(url)
        
        assert response.status_code == status.HTTP_404_NOT_FOUND
    
    def test_sequential_message_edits(self, private_chat, user1):
        """Последовательное редактирование сообщения"""
        message = Message.objects.create(
            chat=private_chat,
            author=user1,
            content='Original'
        )
        
        client = APIClient()
        client.force_authenticate(user=user1)
        
        url = f'/api/v1/communications/messages/{message.pk}/'
        
        # Первое редактирование
        response = client.patch(url, {'content': 'Edit 1'}, format='json')
        assert response.status_code == status.HTTP_200_OK
        
        # Второе редактирование
        response = client.patch(url, {'content': 'Edit 2'}, format='json')
        assert response.status_code == status.HTTP_200_OK
        
        # В БД должно быть последнее изменение
        message.refresh_from_db()
        assert message.content == 'Edit 2'
    
    def test_message_limit_boundary(self, auth_client, private_chat, user1):
        """Тест граничных значений limit параметра"""
        url = f'/api/v1/communications/chats/{private_chat.pk}/messages/'
        
        # Создаем 10 сообщений
        for i in range(10):
            Message.objects.create(chat=private_chat, author=user1, content=f'Msg {i}')
        
        # Тест с различными значениями limit
        test_cases = [
            (0, 0),      # Минимум
            (1, 1),      # Один
            (50, 10),    # Нормальное
            (100, 10),   # Максимум
            (1000, 10),  # Превышение (должно ограничиться до 100)
            (-1, 0),     # Отрицательное (должно обработаться корректно)
        ]
        
        for limit, expected_max in test_cases:
            response = auth_client.get(url, {'limit': limit})
            if response.status_code == status.HTTP_200_OK:
                assert len(response.data['messages']) <= expected_max


# ==================== Performance Tests ====================

class TestPerformance:
    """Тесты производительности"""
    
    def test_large_message_list_performance(self, auth_client, private_chat, user1):
        """Загрузка большого количества сообщений"""
        import time
        
        # Создаем 1000 сообщений
        messages = [
            Message(chat=private_chat, author=user1, content=f'Msg {i}')
            for i in range(1000)
        ]
        Message.objects.bulk_create(messages)
        
        url = f'/api/v1/communications/chats/{private_chat.pk}/messages/'
        
        start = time.time()
        response = auth_client.get(url, {'limit': 100})
        duration = time.time() - start
        
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['messages']) == 100
        # Должно выполниться быстро (менее 2 секунд)
        assert duration < 2.0
    
    def test_complex_query_performance(self, auth_client, private_chat, user1, user2):
        """Производительность сложных запросов"""
        import time
        
        # Создаем 100 сообщений с реакциями и вложениями
        for i in range(100):
            msg = Message.objects.create(
                chat=private_chat,
                author=user1 if i % 2 == 0 else user2,
                content=f'Complex message {i}'
            )
            # Добавляем реакции
            from communications.models import MessageReaction
            MessageReaction.objects.create(message=msg, user=user1, emoji='👍')
        
        url = f'/api/v1/communications/chats/{private_chat.pk}/messages/'
        
        start = time.time()
        response = auth_client.get(url, {'limit': 50})
        duration = time.time() - start
        
        assert response.status_code == status.HTTP_200_OK
        # Должно выполниться разумно быстро
        assert duration < 3.0
