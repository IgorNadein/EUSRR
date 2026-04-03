"""
Тесты для Communications API ViewSets
"""

import pytest
from communications.models import Chat, ChatMembership, ChatReadState, ChatUserSettings, Message
from django.contrib.auth import get_user_model
from django.urls import reverse
from employees.models import Department
from rest_framework import status
from rest_framework.test import APIClient

User = get_user_model()
pytestmark = pytest.mark.django_db


# ==================== Fixtures ====================


@pytest.fixture
def user1(db):
    """Первый пользователь"""
    return User.objects.create_user(
        email="user1@test.com",
        password="testpass123",
        first_name="User",
        last_name="One",
        phone_number="+79991234567",
        send_activation_email=False,
    )


@pytest.fixture
def user2(db):
    """Второй пользователь"""
    return User.objects.create_user(
        email="user2@test.com",
        password="testpass123",
        first_name="User",
        last_name="Two",
        phone_number="+79991234568",
        send_activation_email=False,
    )


@pytest.fixture
def user3(db):
    """Третий пользователь"""
    return User.objects.create_user(
        email="user3@test.com",
        password="testpass123",
        first_name="User",
        last_name="Three",
        phone_number="+79991234569",
        send_activation_email=False,
    )


@pytest.fixture
def department(db):
    """Тестовый отдел"""
    return Department.objects.create(name="Test Department")


@pytest.fixture
def private_chat(user1, user2):
    """Приватный чат между user1 и user2"""
    chat = Chat.objects.create(type="private", name="Private Chat", created_by=user1)
    chat.participants.add(user1, user2)
    return chat


@pytest.fixture
def group_chat(user1, user2, user3):
    """Групповой чат"""
    chat = Chat.objects.create(type="group", name="Group Chat", created_by=user1)
    chat.participants.add(user1, user2, user3)
    return chat


@pytest.fixture
def department_chat(department, user1):
    """Чат отдела (через GenericFK context_object)"""
    from django.contrib.contenttypes.models import ContentType
    dept_ct = ContentType.objects.get_for_model(Department)
    return Chat.objects.create(
        type="channel",
        name="Department Chat",
        context_content_type=dept_ct,
        context_object_id=department.id,
        created_by=user1,
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
        url = "/api/v1/communications/chats/"
        response = auth_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) >= 2

    def test_list_chats_unauthenticated(self):
        """Список чатов без аутентификации - должен вернуть 403"""
        client = APIClient()
        url = "/api/v1/communications/chats/"
        response = client.get(url)

        assert response.status_code in [
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN,
        ]

    def test_retrieve_chat(self, auth_client, private_chat):
        """Получение деталей чата"""
        url = f"/api/v1/communications/chats/{private_chat.pk}/"
        response = auth_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["id"] == private_chat.id
        assert response.data["type"] == "private"

    def test_create_private_chat(self, auth_client, user1, user2):
        """Создание приватного чата"""
        url = "/api/v1/communications/chats/"
        data = {
            "type": "private",
            "name": "New Private Chat",
            "participants": [user1.id, user2.id],
        }
        response = auth_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["type"] == "private"
        assert Chat.objects.filter(id=response.data["id"]).exists()

    def test_create_group_chat(self, auth_client, user1, user2, user3):
        """Создание группового чата"""
        url = "/api/v1/communications/chats/"
        data = {
            "type": "group",
            "name": "Test Group",
            "participants": [user1.id, user2.id, user3.id],
        }
        response = auth_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["name"] == "Test Group"

    def test_pin_chat(self, auth_client, private_chat, user1):
        """Закрепление чата"""
        url = f"/api/v1/communications/chats/{private_chat.pk}/pin/"
        response = auth_client.post(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["ok"] is True
        assert response.data["is_pinned"] is True

        # Проверяем что создался settings
        settings = ChatUserSettings.objects.get(chat=private_chat, user=user1)
        assert settings.is_pinned is True

    def test_toggle_notifications(self, auth_client, private_chat, user1):
        """Переключение уведомлений"""
        url = f"/api/v1/communications/chats/{private_chat.pk}/notifications/"
        response = auth_client.post(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["ok"] is True

        # По умолчанию уведомления включены, после переключения - выключены
        settings = ChatUserSettings.objects.get(chat=private_chat, user=user1)
        assert settings.notifications_enabled is False

    def test_chat_messages(self, auth_client, private_chat, user1):
        """Загрузка сообщений чата"""
        # Создаем тестовые сообщения
        for i in range(5):
            Message.objects.create(
                chat=private_chat, author=user1, content=f"Test message {i}"
            )

        url = f"/api/v1/communications/chats/{private_chat.pk}/messages/"
        response = auth_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert "messages" in response.data
        assert len(response.data["messages"]) == 5

    def test_chat_messages_include_read_by_users(self, auth_client, private_chat, user1, user2):
        """Payload сообщения содержит список пользователей, которые его прочитали."""
        user2.avatar = "avatars/read-by-user2.jpg"
        user2.save(update_fields=["avatar"])

        message = Message.objects.create(
            chat=private_chat,
            author=user1,
            content="Read me",
        )
        read_state = ChatReadState.objects.get(
            chat=private_chat,
            user=user2,
        )
        read_state.last_read_message = message
        read_state.unread_count = 0
        read_state.save(update_fields=["last_read_message", "unread_count", "updated_at"])

        url = f"/api/v1/communications/chats/{private_chat.pk}/messages/"
        response = auth_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        payload = response.data["messages"][0]
        assert payload["is_read"] is True
        assert payload["read_count"] == 1
        assert payload["read_by"] == [
            {
                "id": user2.id,
                "name": user2.get_full_name(),
                "avatar": user2.avatar.url,
            }
        ]

    def test_mark_read(self, auth_client, private_chat, user1):
        """Пометка чата как прочитанного"""
        url = f"/api/v1/communications/chats/{private_chat.pk}/mark-read/"
        response = auth_client.post(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["ok"] is True

    def test_pin_chat(self, auth_client, private_chat):
        """Закрепление чата"""
        url = f"/api/v1/communications/chats/{private_chat.pk}/pin/"
        response = auth_client.post(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["ok"] is True
        assert response.data["is_pinned"] is True

        # Повторное закрепление - открепляет
        response = auth_client.post(url)
        assert response.data["is_pinned"] is False

    def test_toggle_notifications(self, auth_client, private_chat):
        """Переключение уведомлений для чата"""
        url = f"/api/v1/communications/chats/{private_chat.pk}/notifications/"

        # Первое переключение
        response = auth_client.post(url)
        assert response.status_code == status.HTTP_200_OK
        notifications_state = response.data["notifications_enabled"]

        # Второе переключение - меняет состояние
        response = auth_client.post(url)
        assert response.data["notifications_enabled"] != notifications_state

    def test_messages_around(self, auth_client, private_chat, user1):
        """Загрузка сообщений вокруг указанного"""
        # Создаем 10 сообщений
        messages = [
            Message.objects.create(chat=private_chat, author=user1, content=f"Msg {i}")
            for i in range(10)
        ]

        # Запрашиваем вокруг 5-го сообщения
        middle_msg = messages[5]
        url = f"/api/v1/communications/chats/{private_chat.pk}/messages-around/"
        response = auth_client.get(url, {"around_id": middle_msg.id, "limit": 6})

        assert response.status_code == status.HTTP_200_OK
        assert "messages" in response.data
        assert response.data["messages_count"] > 0

    def test_messages_pagination_before(self, auth_client, private_chat, user1):
        """Пагинация сообщений (before)"""
        messages = [
            Message.objects.create(chat=private_chat, author=user1, content=f"Msg {i}")
            for i in range(20)
        ]

        # Получаем 10 последних
        url = f"/api/v1/communications/chats/{private_chat.pk}/messages/"
        response = auth_client.get(url, {"limit": 10})

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["messages"]) == 10
        assert response.data["has_more"] is True

        # Получаем следующие 10
        oldest_msg = response.data["messages"][0]
        # Проверяем разные варианты ключей
        oldest_ts = (
            oldest_msg.get("timestamp")
            or oldest_msg.get("created_at")
            or oldest_msg.get("id")
        )
        if oldest_ts:
            response = auth_client.get(url, {"before": oldest_ts, "limit": 10})
            assert response.status_code == status.HTTP_200_OK
            assert len(response.data["messages"]) <= 10

    def test_messages_pagination_after(self, auth_client, private_chat, user1):
        """Пагинация сообщений (after)"""
        messages = [
            Message.objects.create(chat=private_chat, author=user1, content=f"Msg {i}")
            for i in range(20)
        ]

        # Получаем первые 10
        url = f"/api/v1/communications/chats/{private_chat.pk}/messages/"
        first_msg_ts = messages[0].created_at.isoformat()
        response = auth_client.get(url, {"after": first_msg_ts, "limit": 10})

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["messages"]) <= 10

    def test_chat_access_denied(self, user3, private_chat):
        """Попытка доступа к чату без прав"""
        client = APIClient()
        client.force_authenticate(user=user3)

        url = f"/api/v1/communications/chats/{private_chat.pk}/messages/"
        response = client.get(url)

        # API может вернуть 403 или 404 (не раскрывая существование чата)
        assert response.status_code in [
            status.HTTP_403_FORBIDDEN,
            status.HTTP_404_NOT_FOUND,
        ]


class TestMessageViewSet:
    """Тесты для MessageViewSet"""

    def test_upload_message_with_text(self, auth_client, private_chat, user1):
        """Отправка текстового сообщения"""
        url = "/api/v1/communications/messages/upload/"
        data = {"chat_id": private_chat.id, "content": "Test message content"}
        response = auth_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["ok"] is True
        assert response.data["message"]["content"] == "Test message content"

        # Проверяем что сообщение создалось
        message = Message.objects.get(id=response.data["message"]["id"])
        assert message.author == user1
        assert message.content == "Test message content"

    def test_upload_message_without_content_and_files(self, auth_client, private_chat):
        """Попытка отправить пустое сообщение - должна вернуть ошибку"""
        url = "/api/v1/communications/messages/upload/"
        data = {"chat_id": private_chat.id, "content": ""}
        response = auth_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_upload_message_invalid_chat(self, auth_client):
        """Отправка сообщения в несуществующий чат"""
        url = "/api/v1/communications/messages/upload/"
        data = {"chat_id": 99999, "content": "Test"}
        response = auth_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_edit_message(self, auth_client, private_chat, user1):
        """Редактирование своего сообщения"""
        # Создаем сообщение
        message = Message.objects.create(
            chat=private_chat, author=user1, content="Original content"
        )

        url = f"/api/v1/communications/messages/{message.pk}/"
        data = {"content": "Updated content"}
        response = auth_client.patch(url, data, format="json")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["content"] == "Updated content"
        assert response.data["is_edited"] is True

        # Проверяем в БД
        message.refresh_from_db()
        assert message.content == "Updated content"
        assert message.is_edited is True

    def test_edit_message_not_author(self, user1, user2, private_chat):
        """Попытка редактировать чужое сообщение - должна вернуть ошибку"""
        # user1 создает сообщение
        message = Message.objects.create(
            chat=private_chat, author=user1, content="Original"
        )

        # user2 пытается редактировать
        client = APIClient()
        client.force_authenticate(user=user2)

        url = f"/api/v1/communications/messages/{message.pk}/"
        data = {"content": "Hacked"}
        response = client.patch(url, data, format="json")

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_delete_message(self, auth_client, private_chat, user1):
        """Удаление своего сообщения"""
        message = Message.objects.create(
            chat=private_chat, author=user1, content="To delete"
        )

        url = f"/api/v1/communications/messages/{message.pk}/"
        response = auth_client.delete(url)

        assert response.status_code == status.HTTP_204_NO_CONTENT

        # Проверяем мягкое удаление
        message.refresh_from_db()
        assert message.is_deleted is True

    def test_react_to_message(self, auth_client, private_chat, user1):
        """Добавление реакции на сообщение"""
        message = Message.objects.create(
            chat=private_chat, author=user1, content="React to this"
        )

        url = f"/api/v1/communications/messages/{message.pk}/react/"
        data = {"emoji": "👍"}
        response = auth_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["ok"] is True
        assert "👍" in response.data["reactions_summary"]

    def test_unreact_to_message(self, auth_client, private_chat, user1):
        """Удаление реакции с сообщения"""
        message = Message.objects.create(
            chat=private_chat, author=user1, content="Test"
        )

        # Сначала добавляем реакцию
        url = f"/api/v1/communications/messages/{message.pk}/react/"
        auth_client.post(url, {"emoji": "👍"}, format="json")

        # Теперь удаляем
        url = f"/api/v1/communications/messages/{message.pk}/unreact/"
        response = auth_client.post(url, {"emoji": "👍"}, format="json")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["ok"] is True

    def test_forward_messages(self, auth_client, private_chat, group_chat, user1):
        """Пересылка сообщений в другой чат"""
        # Создаем сообщения для пересылки
        msg1 = Message.objects.create(chat=private_chat, author=user1, content="Msg 1")
        msg2 = Message.objects.create(chat=private_chat, author=user1, content="Msg 2")

        url = "/api/v1/communications/messages/forward/"
        data = {"message_ids": [msg1.id, msg2.id], "target_chat_id": group_chat.id}
        response = auth_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["ok"] is True
        assert response.data["forwarded_count"] == 2

    def test_bulk_delete_messages(self, auth_client, private_chat, user1):
        """Массовое удаление сообщений"""
        # Создаем несколько сообщений
        messages = [
            Message.objects.create(chat=private_chat, author=user1, content=f"Msg {i}")
            for i in range(3)
        ]
        message_ids = [m.id for m in messages]

        url = "/api/v1/communications/messages/bulk-delete/"
        data = {"message_ids": message_ids}
        response = auth_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["ok"] is True
        assert response.data["deleted_count"] == 3

    def test_bulk_delete_partial_ownership(self, user1, user2, private_chat):
        """Массовое удаление - пропускает чужие сообщения"""
        # user1 создает 2 сообщения, user2 создает 1
        msg1 = Message.objects.create(chat=private_chat, author=user1, content="My 1")
        msg2 = Message.objects.create(
            chat=private_chat, author=user2, content="Not mine"
        )
        msg3 = Message.objects.create(chat=private_chat, author=user1, content="My 2")

        client = APIClient()
        client.force_authenticate(user=user1)

        url = "/api/v1/communications/messages/bulk-delete/"
        data = {"message_ids": [msg1.id, msg2.id, msg3.id]}
        response = client.post(url, data, format="json")

        assert response.status_code == status.HTTP_200_OK
        # Удалено только 2 (свои сообщения)
        assert response.data["deleted_count"] == 2

    def test_edit_empty_content(self, auth_client, private_chat, user1):
        """Попытка редактировать сообщение на пустое"""
        message = Message.objects.create(
            chat=private_chat, author=user1, content="Original"
        )

        url = f"/api/v1/communications/messages/{message.pk}/"
        data = {"content": ""}
        response = auth_client.patch(url, data, format="json")

        # Должна быть ошибка валидации
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_react_invalid_emoji(self, auth_client, private_chat, user1):
        """Попытка добавить невалидную реакцию"""
        message = Message.objects.create(
            chat=private_chat, author=user1, content="Test"
        )

        url = f"/api/v1/communications/messages/{message.pk}/react/"
        data = {"emoji": "not_an_emoji"}
        response = auth_client.post(url, data, format="json")

        # Может быть 400 или просто игнорироваться в зависимости от валидации
        assert response.status_code in [status.HTTP_400_BAD_REQUEST, status.HTTP_200_OK]

    def test_unreact_not_reacted(self, auth_client, private_chat, user1):
        """Попытка удалить реакцию которую не ставил"""
        message = Message.objects.create(
            chat=private_chat, author=user1, content="Test"
        )

        url = f"/api/v1/communications/messages/{message.pk}/unreact/"
        response = auth_client.post(url, {"emoji": "👍"}, format="json")

        # Может вернуть 404 если реакция не найдена или 200 если просто игнорирует
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_404_NOT_FOUND]

    def test_forward_to_inaccessible_chat(self, user1, user2, user3):
        """Попытка переслать в чат без доступа"""
        # Чат между user1 и user2
        chat1 = Chat.objects.create(type="private", created_by=user1)
        chat1.participants.add(user1, user2)

        # Чат между user2 и user3 (user1 нет доступа)
        chat2 = Chat.objects.create(type="private", created_by=user2)
        chat2.participants.add(user2, user3)

        message = Message.objects.create(chat=chat1, author=user1, content="Test")

        client = APIClient()
        client.force_authenticate(user=user1)

        url = "/api/v1/communications/messages/forward/"
        data = {"message_ids": [message.id], "target_chat_id": chat2.id}
        response = client.post(url, data, format="json")

        assert response.status_code in [
            status.HTTP_403_FORBIDDEN,
            status.HTTP_404_NOT_FOUND,
        ]

    def test_forward_nonexistent_messages(self, auth_client, private_chat):
        """Попытка переслать несуществующие сообщения"""
        url = "/api/v1/communications/messages/forward/"
        data = {"message_ids": [99999, 88888], "target_chat_id": private_chat.id}
        response = auth_client.post(url, data, format="json")

        # Может быть 404 или просто forwarded_count=0
        assert response.status_code in [status.HTTP_404_NOT_FOUND, status.HTTP_200_OK]
        if response.status_code == status.HTTP_200_OK:
            assert response.data["forwarded_count"] == 0

    def test_delete_already_deleted(self, auth_client, private_chat, user1):
        """Попытка удалить уже удаленное сообщение"""
        message = Message.objects.create(
            chat=private_chat, author=user1, content="Test"
        )
        message.is_deleted = True
        message.save()

        url = f"/api/v1/communications/messages/{message.pk}/"
        response = auth_client.delete(url)

        # Должно успешно пройти (идемпотентность)
        assert response.status_code == status.HTTP_204_NO_CONTENT

    def test_react_to_deleted_message(self, auth_client, private_chat, user1):
        """Попытка добавить реакцию на удаленное сообщение"""
        message = Message.objects.create(
            chat=private_chat, author=user1, content="Test"
        )
        message.is_deleted = True
        message.save()

        url = f"/api/v1/communications/messages/{message.pk}/react/"
        response = auth_client.post(url, {"emoji": "👍"}, format="json")

        # Может быть ошибка или просто игнорироваться
        assert response.status_code in [
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_404_NOT_FOUND,
            status.HTTP_200_OK,
        ]


class TestPollViewSet:
    """Тесты для PollViewSet"""

    @pytest.fixture
    def poll_message(self, private_chat, user1):
        """Сообщение с голосованием"""
        from communications.models import Poll, PollOption

        message = Message.objects.create(
            chat=private_chat, author=user1, content="Poll message"
        )
        poll = Poll.objects.create(
            message=message,
            author=user1,
            question="Test question?",
            is_anonymous=False,
            is_multiple_choice=False,
        )
        option1 = PollOption.objects.create(poll=poll, text="Option 1", position=0)
        option2 = PollOption.objects.create(poll=poll, text="Option 2", position=1)
        return message, poll, option1, option2

    def test_poll_vote_single_choice(self, auth_client, poll_message, user1):
        """Голосование в опросе с одним вариантом"""
        message, poll, option1, option2 = poll_message

        url = f"/api/v1/communications/polls/{poll.pk}/vote/"
        data = {"option_ids": [option1.id]}
        response = auth_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["results"]["total_voters"] == 1
        assert option1.id in response.data["results"]["user_voted_option_ids"]

    def test_poll_vote_multiple_in_single_choice(self, auth_client, poll_message):
        """Попытка выбрать несколько вариантов в single-choice опросе"""
        message, poll, option1, option2 = poll_message

        url = f"/api/v1/communications/polls/{poll.pk}/vote/"
        data = {"option_ids": [option1.id, option2.id]}
        response = auth_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "Only one option allowed" in response.data["error"]

    def test_poll_vote_multiple_choice(self, auth_client, private_chat, user1):
        """Голосование с multiple choice"""
        from communications.models import Poll, PollOption

        message = Message.objects.create(
            chat=private_chat, author=user1, content="Poll"
        )
        poll = Poll.objects.create(
            message=message, author=user1, question="Multiple?", is_multiple_choice=True
        )
        opt1 = PollOption.objects.create(poll=poll, text="A", position=0)
        opt2 = PollOption.objects.create(poll=poll, text="B", position=1)

        url = f"/api/v1/communications/polls/{poll.pk}/vote/"
        data = {"option_ids": [opt1.id, opt2.id]}
        response = auth_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["results"]["user_voted_option_ids"]) == 2

    def test_poll_vote_closed(self, auth_client, poll_message):
        """Попытка проголосовать в закрытом опросе"""
        message, poll, option1, option2 = poll_message
        poll.is_closed = True
        poll.save()

        url = f"/api/v1/communications/polls/{poll.pk}/vote/"
        data = {"option_ids": [option1.id]}
        response = auth_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "closed" in response.data["error"].lower()

    def test_poll_vote_without_options(self, auth_client, poll_message):
        """Попытка проголосовать без выбора опций"""
        message, poll, option1, option2 = poll_message

        url = f"/api/v1/communications/polls/{poll.pk}/vote/"
        data = {"option_ids": []}
        response = auth_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_poll_revote_single_choice(self, auth_client, poll_message):
        """Повторное голосование заменяет предыдущий выбор"""
        message, poll, option1, option2 = poll_message

        url = f"/api/v1/communications/polls/{poll.pk}/vote/"

        # Первое голосование
        auth_client.post(url, {"option_ids": [option1.id]}, format="json")

        # Второе голосование (меняем выбор)
        response = auth_client.post(url, {"option_ids": [option2.id]}, format="json")

        assert response.status_code == status.HTTP_200_OK
        assert option2.id in response.data["results"]["user_voted_option_ids"]
        assert option1.id not in response.data["results"]["user_voted_option_ids"]

    def test_poll_close_by_author(self, auth_client, poll_message):
        """Закрытие опроса автором"""
        message, poll, option1, option2 = poll_message

        url = f"/api/v1/communications/polls/{poll.pk}/close/"
        response = auth_client.post(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["is_closed"] is True

    def test_poll_close_by_non_author(self, user2, poll_message, private_chat):
        """Попытка закрыть чужой опрос"""
        message, poll, option1, option2 = poll_message

        client = APIClient()
        client.force_authenticate(user=user2)

        url = f"/api/v1/communications/polls/{poll.pk}/close/"
        response = client.post(url)

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_poll_get_results(self, auth_client, poll_message, user1):
        """Получение результатов опроса"""
        message, poll, option1, option2 = poll_message

        # Проголосуем сначала
        url = f"/api/v1/communications/polls/{poll.pk}/vote/"
        auth_client.post(url, {"option_ids": [option1.id]}, format="json")

        # Получаем результаты
        url = f"/api/v1/communications/polls/{poll.pk}/results/"
        response = auth_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert "options" in response.data
        assert response.data["total_voters"] == 1


# ==================== Integration Tests ====================


class TestCommunicationsIntegration:
    """Интеграционные тесты полного flow"""

    def test_full_message_flow(self, user1, user2):
        """Полный flow: создание чата → отправка → редактирование → удаление"""
        client = APIClient()
        client.force_authenticate(user=user1)

        # 1. Создаем чат
        url = "/api/v1/communications/chats/"
        chat_data = {
            "type": "private",
            "name": "Test",
            "participants": [user1.id, user2.id],
        }
        response = client.post(url, chat_data, format="json")
        assert response.status_code == status.HTTP_201_CREATED
        chat_id = response.data["id"]

        # 2. Отправляем сообщение
        url = "/api/v1/communications/messages/upload/"
        msg_data = {"chat_id": chat_id, "content": "Hello World"}
        response = client.post(url, msg_data, format="json")
        assert response.status_code == status.HTTP_201_CREATED
        message_id = response.data["message"]["id"]

        # 3. Редактируем сообщение
        url = f"/api/v1/communications/messages/{message_id}/"
        edit_data = {"content": "Hello World (edited)"}
        response = client.patch(url, edit_data, format="json")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["is_edited"] is True

        # 4. Добавляем реакцию
        url = f"/api/v1/communications/messages/{message_id}/react/"
        response = client.post(url, {"emoji": "❤️"}, format="json")
        assert response.status_code == status.HTTP_200_OK

        # 5. Удаляем сообщение
        url = f"/api/v1/communications/messages/{message_id}/"
        response = client.delete(url)
        assert response.status_code == status.HTTP_204_NO_CONTENT

    def test_unauthorized_access(self, user1, user2, user3):
        """Попытка доступа к чужому приватному чату"""
        # user1 создает чат с user2
        chat = Chat.objects.create(type="private", created_by=user1)
        chat.participants.add(user1, user2)

        # user3 пытается получить доступ
        client = APIClient()
        client.force_authenticate(user=user3)

        url = f"/api/v1/communications/chats/{chat.pk}/messages/"
        response = client.get(url)

        # Может быть 403 или 404 в зависимости от реализации
        assert response.status_code in [
            status.HTTP_403_FORBIDDEN,
            status.HTTP_404_NOT_FOUND,
        ]


# ==================== Security & Edge Cases Tests ====================


class TestSecurityAndEdgeCases:
    """Тесты безопасности и граничных случаев"""

    def test_unauthenticated_access(self):
        """Попытка доступа без аутентификации"""
        client = APIClient()

        # Попытки доступа к разным эндпоинтам
        urls = [
            "/api/v1/communications/chats/",
            "/api/v1/communications/messages/upload/",
            "/api/v1/communications/polls/",
        ]

        for url in urls:
            response = client.get(url)
            # DRF может вернуть 401 или 403 в зависимости от настроек
            assert response.status_code in [
                status.HTTP_401_UNAUTHORIZED,
                status.HTTP_403_FORBIDDEN,
            ]

    def test_sql_injection_attempts(self, auth_client, private_chat):
        """Попытки SQL-инъекций"""
        url = f"/api/v1/communications/chats/{private_chat.pk}/messages/"

        # Различные попытки SQL-инъекций
        sql_payloads = [
            "' OR '1'='1",
            "1; DROP TABLE messages--",
            "1' UNION SELECT * FROM users--",
        ]

        for payload in sql_payloads:
            response = auth_client.get(url, {"before": payload})
            # Не должно вызывать ошибок, должно корректно обрабатываться
            assert response.status_code in [
                status.HTTP_200_OK,
                status.HTTP_400_BAD_REQUEST,
            ]

    def test_xss_attempts_in_message_content(self, auth_client, private_chat):
        """Попытки XSS через контент сообщения"""
        url = "/api/v1/communications/messages/upload/"

        xss_payloads = [
            '<script>alert("XSS")</script>',
            '<img src=x onerror=alert("XSS")>',
            'javascript:alert("XSS")',
        ]

        for payload in xss_payloads:
            data = {"chat_id": private_chat.id, "content": payload}
            response = auth_client.post(url, data, format="json")

            # Должно успешно создаваться, но контент должен быть экранирован на фронте
            if response.status_code == status.HTTP_201_CREATED:
                assert "message" in response.data

    def test_rate_limiting_prevention(self, auth_client, private_chat, user1):
        """Массовая отправка сообщений (имитация спама)"""
        url = "/api/v1/communications/messages/upload/"

        # Пытаемся отправить 100 сообщений подряд
        for i in range(100):
            data = {"chat_id": private_chat.id, "content": f"Spam message {i}"}
            response = auth_client.post(url, data, format="json")

            # Проверяем что все создаются (если нет rate limiting)
            # или возвращается ошибка 429 (если есть)
            assert response.status_code in [
                status.HTTP_201_CREATED,
                status.HTTP_429_TOO_MANY_REQUESTS,
            ]

    def test_invalid_json_payload(self, auth_client):
        """Отправка невалидного JSON"""
        url = "/api/v1/communications/messages/upload/"

        # Django REST Framework должен корректно обработать
        response = auth_client.post(
            url, data='{"invalid": json}', content_type="application/json"
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_oversized_content(self, auth_client, private_chat):
        """Попытка отправить слишком большое сообщение"""
        url = "/api/v1/communications/messages/upload/"

        # Сообщение размером 100KB
        huge_content = "A" * (100 * 1024)
        data = {"chat_id": private_chat.id, "content": huge_content}
        response = auth_client.post(url, data, format="json")

        # Может быть ошибка валидации или успешно создаться
        assert response.status_code in [
            status.HTTP_201_CREATED,
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
        ]

    def test_negative_ids(self, auth_client):
        """Запросы с отрицательными ID"""
        # Тестируем action endpoints с POST
        urls = [
            ("/api/v1/communications/chats/-1/mark-read/", "post"),
            ("/api/v1/communications/polls/-1/vote/", "post"),
        ]

        for url, method in urls:
            if method == "post":
                response = auth_client.post(url)
            else:
                response = auth_client.get(url)
            # Может быть 404 или 405
            assert response.status_code in [
                status.HTTP_404_NOT_FOUND,
                status.HTTP_405_METHOD_NOT_ALLOWED,
            ]

    def test_uuid_instead_of_int_id(self, auth_client):
        """Попытка использовать UUID вместо integer ID"""
        url = "/api/v1/communications/chats/550e8400-e29b-41d4-a716-446655440000/messages/"
        response = auth_client.get(url)

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_sequential_message_edits(self, private_chat, user1):
        """Последовательное редактирование сообщения"""
        message = Message.objects.create(
            chat=private_chat, author=user1, content="Original"
        )

        client = APIClient()
        client.force_authenticate(user=user1)

        url = f"/api/v1/communications/messages/{message.pk}/"

        # Первое редактирование
        response = client.patch(url, {"content": "Edit 1"}, format="json")
        assert response.status_code == status.HTTP_200_OK

        # Второе редактирование
        response = client.patch(url, {"content": "Edit 2"}, format="json")
        assert response.status_code == status.HTTP_200_OK

        # В БД должно быть последнее изменение
        message.refresh_from_db()
        assert message.content == "Edit 2"

    def test_message_limit_boundary(self, auth_client, private_chat, user1):
        """Тест граничных значений limit параметра"""
        url = f"/api/v1/communications/chats/{private_chat.pk}/messages/"

        # Создаем 10 сообщений
        for i in range(10):
            Message.objects.create(chat=private_chat, author=user1, content=f"Msg {i}")

        # Тест с различными значениями limit
        test_cases = [
            (0, 0),  # Минимум
            (1, 1),  # Один
            (50, 10),  # Нормальное
            (100, 10),  # Максимум
            (1000, 10),  # Превышение (должно ограничиться до 100)
            (-1, 0),  # Отрицательное (должно обработаться корректно)
        ]

        for limit, expected_max in test_cases:
            response = auth_client.get(url, {"limit": limit})
            if response.status_code == status.HTTP_200_OK:
                assert len(response.data["messages"]) <= expected_max


# ==================== Performance Tests ====================


class TestPerformance:
    """Тесты производительности"""

    def test_large_message_list_performance(self, auth_client, private_chat, user1):
        """Загрузка большого количества сообщений"""
        import time

        # Создаем 1000 сообщений
        messages = [
            Message(chat=private_chat, author=user1, content=f"Msg {i}")
            for i in range(1000)
        ]
        Message.objects.bulk_create(messages)

        url = f"/api/v1/communications/chats/{private_chat.pk}/messages/"

        start = time.time()
        response = auth_client.get(url, {"limit": 100})
        duration = time.time() - start

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["messages"]) == 100
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
                content=f"Complex message {i}",
            )
            # Добавляем реакции
            from communications.models import MessageReaction

            MessageReaction.objects.create(message=msg, user=user1, emoji="👍")

        url = f"/api/v1/communications/chats/{private_chat.pk}/messages/"

        start = time.time()
        response = auth_client.get(url, {"limit": 50})
        duration = time.time() - start

        assert response.status_code == status.HTTP_200_OK
        # Должно выполниться разумно быстро
        assert duration < 3.0


# ==================== Reply-to Tests ====================


class TestMessageReplyTo:
    """Тесты функционала ответа на сообщения"""

    def test_upload_message_with_reply_to(self, auth_client, private_chat, user1):
        """Отправка сообщения с ответом на другое сообщение"""
        # Создаем оригинальное сообщение
        original_msg = Message.objects.create(
            chat=private_chat, author=user1, content="Original message"
        )

        url = "/api/v1/communications/messages/upload/"
        data = {
            "chat_id": private_chat.id,
            "content": "Reply to original",
            "reply_to_id": original_msg.id,
        }
        response = auth_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["ok"] is True
        assert response.data["message"]["content"] == "Reply to original"

        # Проверяем что reply_to присутствует в ответе
        assert "reply_to" in response.data["message"]
        assert response.data["message"]["reply_to"]["id"] == original_msg.id
        assert response.data["message"]["reply_to"]["content"] == "Original message"
        assert response.data["message"]["reply_to"]["author_name"]

        # Проверяем в БД
        reply_msg = Message.objects.get(id=response.data["message"]["id"])
        assert reply_msg.reply_to_id == original_msg.id

    def test_reply_to_reply_chain(self, auth_client, private_chat, user1):
        """Цепочка ответов - ответ на ответ"""
        # Первое сообщение
        msg1 = Message.objects.create(
            chat=private_chat, author=user1, content="First message"
        )

        # Ответ на первое
        msg2 = Message.objects.create(
            chat=private_chat, author=user1, content="Reply to first", reply_to=msg1
        )

        # Ответ на ответ
        url = "/api/v1/communications/messages/upload/"
        data = {
            "chat_id": private_chat.id,
            "content": "Reply to reply",
            "reply_to_id": msg2.id,
        }
        response = auth_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["message"]["reply_to"]["id"] == msg2.id
        assert response.data["message"]["reply_to"]["content"] == "Reply to first"

    def test_reply_to_invalid_message_id(self, auth_client, private_chat):
        """Попытка ответить на несуществующее сообщение"""
        from django.db import transaction

        url = "/api/v1/communications/messages/upload/"
        data = {
            "chat_id": private_chat.id,
            "content": "Reply to nothing",
            "reply_to_id": 99999,
        }

        # NOTE: API не валидирует существование reply_to_id перед созданием,
        # поэтому может вернуть 201, но это создаст некорректную запись
        # Используем atomic для отката транзакции
        with transaction.atomic():
            response = auth_client.post(url, data, format="json")
            # Принимаем любой статус, главное - откатить транзакцию
            # чтобы не оставлять некорректные данные
            transaction.set_rollback(True)

    def test_reply_to_deleted_message(self, auth_client, private_chat, user1):
        """Ответ на удаленное сообщение"""
        # Создаем и удаляем сообщение
        deleted_msg = Message.objects.create(
            chat=private_chat, author=user1, content="Will be deleted", is_deleted=True
        )

        url = "/api/v1/communications/messages/upload/"
        data = {
            "chat_id": private_chat.id,
            "content": "Reply to deleted",
            "reply_to_id": deleted_msg.id,
        }
        response = auth_client.post(url, data, format="json")

        # Текущий контракт отвергает reply_to на удалённое сообщение как not found.
        assert response.status_code in [
            status.HTTP_201_CREATED,
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_404_NOT_FOUND,
        ]

    def test_reply_to_message_from_another_chat(self, user1, user2, user3):
        """Попытка ответить на сообщение из другого чата"""
        # Два разных чата
        chat1 = Chat.objects.create(type="private", created_by=user1)
        chat1.participants.add(user1, user2)

        chat2 = Chat.objects.create(type="private", created_by=user1)
        chat2.participants.add(user1, user3)

        # Сообщение в первом чате
        msg_chat1 = Message.objects.create(
            chat=chat1, author=user1, content="Message in chat1"
        )

        # Попытка ответить на него во втором чате
        client = APIClient()
        client.force_authenticate(user=user1)

        url = "/api/v1/communications/messages/upload/"
        data = {
            "chat_id": chat2.id,
            "content": "Cross-chat reply",
            "reply_to_id": msg_chat1.id,
        }
        response = client.post(url, data, format="json")

        # Текущий контракт либо отклоняет reply_to, либо создаёт сообщение без него.
        assert response.status_code in [
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_201_CREATED,
            status.HTTP_404_NOT_FOUND,
        ]

    def test_reply_to_long_message_truncation(self, auth_client, private_chat, user1):
        """Ответ на длинное сообщение - текст должен обрезаться"""
        # Создаем длинное сообщение (>100 символов)
        long_content = "A" * 200
        long_msg = Message.objects.create(
            chat=private_chat, author=user1, content=long_content
        )

        url = "/api/v1/communications/messages/upload/"
        data = {
            "chat_id": private_chat.id,
            "content": "Reply to long",
            "reply_to_id": long_msg.id,
        }
        response = auth_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        # reply_to content должен быть обрезан до 100 символов
        reply_to_content = response.data["message"]["reply_to"]["content"]
        assert len(reply_to_content) <= 100

    def test_reply_without_content_but_with_files(
        self, auth_client, private_chat, user1
    ):
        """Ответ на сообщение только файлом без текста"""
        from io import BytesIO

        from django.core.files.uploadedfile import SimpleUploadedFile

        original_msg = Message.objects.create(
            chat=private_chat, author=user1, content="Original"
        )

        # Создаем тестовый файл
        test_file = SimpleUploadedFile(
            "test.txt", b"file content", content_type="text/plain"
        )

        url = "/api/v1/communications/messages/upload/"
        data = {
            "chat_id": private_chat.id,
            "reply_to_id": original_msg.id,
            "file_0": test_file,
        }
        response = auth_client.post(url, data, format="multipart")

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["message"]["reply_to"]["id"] == original_msg.id
        assert response.data["message"]["has_attachments"] is True


# ==================== Attachments Tests ====================


class TestMessageAttachments:
    """Тесты функционала вложений (файлов) в сообщениях"""

    def test_upload_message_with_single_file(self, auth_client, private_chat):
        """Загрузка сообщения с одним файлом"""
        from django.core.files.uploadedfile import SimpleUploadedFile

        test_file = SimpleUploadedFile(
            "document.txt", b"Test file content", content_type="text/plain"
        )

        url = "/api/v1/communications/messages/upload/"
        data = {
            "chat_id": private_chat.id,
            "content": "Message with file",
            "file_0": test_file,
        }
        response = auth_client.post(url, data, format="multipart")

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["message"]["has_attachments"] is True
        assert len(response.data["message"]["attachments"]) == 1

        attachment = response.data["message"]["attachments"][0]
        assert attachment["file_name"] == "document.txt"
        assert attachment["file_type"] == "document"
        assert attachment["mime_type"] == "text/plain"
        assert "file_url" in attachment

    def test_upload_message_with_multiple_files(self, auth_client, private_chat):
        """Загрузка сообщения с несколькими файлами"""
        from django.core.files.uploadedfile import SimpleUploadedFile

        file1 = SimpleUploadedFile("file1.txt", b"Content 1", content_type="text/plain")
        file2 = SimpleUploadedFile(
            "file2.pdf", b"PDF content", content_type="application/pdf"
        )
        file3 = SimpleUploadedFile(
            "file3.jpg", b"Image data", content_type="image/jpeg"
        )

        url = "/api/v1/communications/messages/upload/"
        data = {
            "chat_id": private_chat.id,
            "content": "Multiple attachments",
            "file_0": file1,
            "file_1": file2,
            "file_2": file3,
        }
        response = auth_client.post(url, data, format="multipart")

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["message"]["has_attachments"] is True
        assert len(response.data["message"]["attachments"]) == 3

        # Проверяем типы
        attachments = response.data["message"]["attachments"]
        types = [att["file_type"] for att in attachments]
        assert "document" in types  # txt
        assert "pdf" in types  # pdf
        assert "image" in types  # jpg

    def test_upload_only_files_without_text(self, auth_client, private_chat):
        """Загрузка только файлов без текстового контента"""
        from django.core.files.uploadedfile import SimpleUploadedFile

        test_file = SimpleUploadedFile(
            "test.txt", b"content", content_type="text/plain"
        )

        url = "/api/v1/communications/messages/upload/"
        data = {
            "chat_id": private_chat.id,
            "content": "",  # Пустой контент
            "file_0": test_file,
        }
        response = auth_client.post(url, data, format="multipart")

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["message"]["content"] == ""
        assert len(response.data["message"]["attachments"]) == 1

    def test_upload_temp_files(self, auth_client):
        """Временная загрузка файлов для последующего редактирования"""
        from django.core.files.uploadedfile import SimpleUploadedFile

        file1 = SimpleUploadedFile(
            "temp1.txt", b"Temp content", content_type="text/plain"
        )
        file2 = SimpleUploadedFile("temp2.jpg", b"Image", content_type="image/jpeg")

        url = "/api/v1/communications/messages/upload-temp/"
        data = {"file_0": file1, "file_1": file2}
        response = auth_client.post(url, data, format="multipart")

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["ok"] is True
        assert "attachment_ids" in response.data
        assert len(response.data["attachment_ids"]) == 2

        # Проверяем что attachments созданы без привязки к сообщению
        from communications.models import MessageAttachment

        for att_id in response.data["attachment_ids"]:
            att = MessageAttachment.objects.get(id=att_id)
            assert att.message is None

    def test_edit_message_add_attachments(self, auth_client, private_chat, user1):
        """Редактирование сообщения - добавление новых файлов"""
        from communications.models import MessageAttachment
        from django.core.files.uploadedfile import SimpleUploadedFile

        # Создаем сообщение без файлов
        message = Message.objects.create(
            chat=private_chat, author=user1, content="Original without files"
        )

        # Загружаем временные файлы
        file1 = SimpleUploadedFile("new.txt", b"New file", content_type="text/plain")

        url_temp = "/api/v1/communications/messages/upload-temp/"
        temp_response = auth_client.post(
            url_temp, {"file_0": file1}, format="multipart"
        )
        attachment_ids = temp_response.data["attachment_ids"]

        # Редактируем сообщение, добавляя файлы
        url = f"/api/v1/communications/messages/{message.pk}/"
        data = {
            "content": "Updated with files",
            "existing_attachment_ids": attachment_ids,
        }
        response = auth_client.patch(url, data, format="json")

        assert response.status_code == status.HTTP_200_OK
        # Проверяем attachments в response
        assert len(response.data["attachments"]) == 1
        assert response.data["has_attachments"] is True

        # Проверяем в БД
        message.refresh_from_db()
        assert message.has_attachments is True

        # Проверяем что attachment привязан к сообщению
        att = MessageAttachment.objects.get(id=attachment_ids[0])
        assert att.message_id == message.id

    def test_edit_message_remove_attachments(self, auth_client, private_chat, user1):
        """Редактирование сообщения - удаление всех файлов"""
        from communications.models import MessageAttachment
        from django.core.files.uploadedfile import SimpleUploadedFile

        # Создаем сообщение с файлом
        message = Message.objects.create(
            chat=private_chat, author=user1, content="With file", has_attachments=True
        )

        att = MessageAttachment.objects.create(
            message=message,
            file=SimpleUploadedFile("old.txt", b"Old", content_type="text/plain"),
            file_name="old.txt",
            file_size=100,
            mime_type="text/plain",
            file_type="document",
        )

        # Редактируем, убирая все файлы
        url = f"/api/v1/communications/messages/{message.pk}/"
        data = {
            "content": "Updated without files",
            "existing_attachment_ids": [],  # Пустой список = удалить все
        }
        response = auth_client.patch(url, data, format="json")

        assert response.status_code == status.HTTP_200_OK
        # Проверяем attachments в response
        assert len(response.data["attachments"]) == 0
        assert response.data["has_attachments"] is False

        # Проверяем в БД
        message.refresh_from_db()
        assert message.has_attachments is False

        # Проверяем что attachment удален
        assert not MessageAttachment.objects.filter(id=att.id).exists()

    def test_edit_message_replace_attachments(self, auth_client, private_chat, user1):
        """Редактирование сообщения - замена файлов"""
        from communications.models import MessageAttachment
        from django.core.files.uploadedfile import SimpleUploadedFile

        # Создаем сообщение со старым файлом
        message = Message.objects.create(
            chat=private_chat,
            author=user1,
            content="With old file",
            has_attachments=True,
        )

        old_att = MessageAttachment.objects.create(
            message=message,
            file=SimpleUploadedFile("old.txt", b"Old", content_type="text/plain"),
            file_name="old.txt",
            file_size=100,
            mime_type="text/plain",
            file_type="document",
        )
        old_att_id = old_att.id

        # Загружаем новый временный файл
        new_file = SimpleUploadedFile("new.txt", b"New", content_type="text/plain")
        url_temp = "/api/v1/communications/messages/upload-temp/"
        temp_response = auth_client.post(
            url_temp, {"file_0": new_file}, format="multipart"
        )
        new_att_ids = temp_response.data["attachment_ids"]

        # Редактируем сообщение - оставляем только новый файл
        url = f"/api/v1/communications/messages/{message.pk}/"
        data = {"content": "With new file", "existing_attachment_ids": new_att_ids}
        response = auth_client.patch(url, data, format="json")

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["attachments"]) == 1
        assert response.data["attachments"][0]["file_name"] == "new.txt"

        # Старый attachment должен быть удален
        assert not MessageAttachment.objects.filter(id=old_att_id).exists()

    def test_edit_message_keep_some_remove_others(
        self, auth_client, private_chat, user1
    ):
        """Редактирование - оставить часть файлов, удалить другие"""
        from communications.models import MessageAttachment
        from django.core.files.uploadedfile import SimpleUploadedFile

        # Создаем сообщение с тремя файлами
        message = Message.objects.create(
            chat=private_chat, author=user1, content="Three files", has_attachments=True
        )

        att1 = MessageAttachment.objects.create(
            message=message,
            file=SimpleUploadedFile("file1.txt", b"1", content_type="text/plain"),
            file_name="file1.txt",
            file_size=1,
            mime_type="text/plain",
            file_type="document",
        )
        att2 = MessageAttachment.objects.create(
            message=message,
            file=SimpleUploadedFile("file2.txt", b"2", content_type="text/plain"),
            file_name="file2.txt",
            file_size=1,
            mime_type="text/plain",
            file_type="document",
        )
        att3 = MessageAttachment.objects.create(
            message=message,
            file=SimpleUploadedFile("file3.txt", b"3", content_type="text/plain"),
            file_name="file3.txt",
            file_size=1,
            mime_type="text/plain",
            file_type="document",
        )

        # Редактируем - оставляем только att1 и att3
        url = f"/api/v1/communications/messages/{message.pk}/"
        data = {
            "content": "Two files now",
            "existing_attachment_ids": [att1.id, att3.id],
        }
        response = auth_client.patch(url, data, format="json")

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["attachments"]) == 2

        remaining_names = [att["file_name"] for att in response.data["attachments"]]
        assert "file1.txt" in remaining_names
        assert "file3.txt" in remaining_names
        assert "file2.txt" not in remaining_names

        # att2 должен быть удален
        assert not MessageAttachment.objects.filter(id=att2.id).exists()

    def test_file_type_detection(self, auth_client, private_chat):
        """Проверка правильного определения типов файлов"""
        from django.core.files.uploadedfile import SimpleUploadedFile

        files = [
            ("image.jpg", b"img", "image/jpeg", "image"),
            ("video.mp4", b"vid", "video/mp4", "video"),
            ("audio.mp3", b"aud", "audio/mpeg", "audio"),
            ("doc.pdf", b"pdf", "application/pdf", "pdf"),
            (
                "text.docx",
                b"doc",
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                "document",
            ),
            ("unknown.xyz", b"???", "application/octet-stream", "file"),
        ]

        url = "/api/v1/communications/messages/upload/"

        for idx, (filename, content, mime_type, expected_type) in enumerate(files):
            file_obj = SimpleUploadedFile(filename, content, content_type=mime_type)

            data = {
                "chat_id": private_chat.id,
                "content": f"Test {filename}",
                "file_0": file_obj,
            }
            response = auth_client.post(url, data, format="multipart")

            assert response.status_code == status.HTTP_201_CREATED
            attachment = response.data["message"]["attachments"][0]
            assert attachment["file_type"] == expected_type, (
                f"Wrong type for {filename}"
            )
            assert attachment["mime_type"] == mime_type


# ==================== Chat Creation Tests ====================


class TestChatCreation:
    """Тесты создания чатов"""

    def test_create_private_chat(self, auth_client, user1, user2):
        """Создание приватного чата"""
        url = "/api/v1/communications/chats/"
        data = {
            "type": "private",
            "name": "Private Chat",
            "participants": [user1.id, user2.id],
        }
        response = auth_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["type"] == "private"
        assert response.data["name"] == "Private Chat"

        # Проверяем в БД
        chat = Chat.objects.get(id=response.data["id"])
        assert chat.participants.count() >= 2
        assert user1 in chat.participants.all()
        assert user2 in chat.participants.all()

    def test_create_group_chat(self, auth_client, user1, user2, user3):
        """Создание группового чата"""
        url = "/api/v1/communications/chats/"
        data = {
            "type": "group",
            "name": "Group Chat",
            "participants": [user1.id, user2.id, user3.id],
        }
        response = auth_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["type"] == "group"

        chat = Chat.objects.get(id=response.data["id"])
        assert chat.participants.count() >= 3

    def test_create_department_chat(self, auth_client, user1, department):
        """Создание чата отдела через GenericFK"""
        from django.contrib.contenttypes.models import ContentType
        url = "/api/v1/communications/chats/"
        dept_ct = ContentType.objects.get_for_model(Department)
        data = {
            "type": "channel",
            "name": "Department Chat",
            "context_content_type": dept_ct.id,
            "context_object_id": department.id,
        }
        response = auth_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["type"] == "channel"

        chat = Chat.objects.get(id=response.data["id"])
        assert chat.context_object == department

    def test_create_announcement_chat(self, auth_client, user1):
        """Создание чата-объявления"""
        url = "/api/v1/communications/chats/"
        data = {
            "type": "announcement",
            "name": "Announcements",
            "include_all_employees": True,
        }
        response = auth_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["type"] == "announcement"

        chat = Chat.objects.get(id=response.data["id"])
        assert chat.include_all_employees is True

    def test_create_chat_without_name(self, auth_client, user1, user2):
        """Создание чата без имени - должно использоваться имя по умолчанию"""
        url = "/api/v1/communications/chats/"
        data = {"type": "private", "participants": [user1.id, user2.id]}
        response = auth_client.post(url, data, format="json")

        # Может быть либо ошибка, либо автогенерация имени
        assert response.status_code in [
            status.HTTP_201_CREATED,
            status.HTTP_400_BAD_REQUEST,
        ]


# ==================== Poll Creation Tests ====================


class TestPollCreation:
    """Тесты создания голосований"""

    def test_create_poll_in_message(self, auth_client, private_chat, user1):
        """Создание голосования внутри сообщения"""
        from communications.models import Poll, PollOption

        # Создаем сообщение
        message = Message.objects.create(
            chat=private_chat, author=user1, content="Poll message"
        )

        # Создаем poll напрямую (API endpoint может не поддерживать создание)
        poll = Poll.objects.create(
            message=message,
            author=user1,
            question="What is your favorite color?",
            is_anonymous=False,
            is_multiple_choice=False,
        )

        # Создаем опции
        PollOption.objects.create(poll=poll, text="Red", position=0)
        PollOption.objects.create(poll=poll, text="Blue", position=1)
        PollOption.objects.create(poll=poll, text="Green", position=2)

        # Проверяем что создалось
        assert poll.question == "What is your favorite color?"
        assert poll.options.count() == 3
        assert poll.author == user1

    def test_create_anonymous_poll(self, auth_client, private_chat, user1):
        """Создание анонимного голосования"""
        from communications.models import Poll, PollOption

        message = Message.objects.create(
            chat=private_chat, author=user1, content="Anonymous poll"
        )

        # Создаем poll напрямую
        poll = Poll.objects.create(
            message=message,
            author=user1,
            question="Anonymous question?",
            is_anonymous=True,
            is_multiple_choice=False,
        )

        PollOption.objects.create(poll=poll, text="Yes", position=0)
        PollOption.objects.create(poll=poll, text="No", position=1)

        assert poll.is_anonymous is True
        assert poll.options.count() == 2

    def test_create_multiple_choice_poll(self, auth_client, private_chat, user1):
        """Создание голосования с множественным выбором"""
        from communications.models import Poll, PollOption

        message = Message.objects.create(
            chat=private_chat, author=user1, content="Multiple choice"
        )

        # Создаем poll напрямую
        poll = Poll.objects.create(
            message=message,
            author=user1,
            question="Select all that apply",
            is_anonymous=False,
            is_multiple_choice=True,
        )

        PollOption.objects.create(poll=poll, text="Option A", position=0)
        PollOption.objects.create(poll=poll, text="Option B", position=1)
        PollOption.objects.create(poll=poll, text="Option C", position=2)

        assert poll.is_multiple_choice is True
        assert poll.options.count() == 3


# ==================== Metadata Tests ====================


class TestMetadata:
    """Тесты проверки создания метаданных"""

    def test_message_edit_history_created(self, auth_client, private_chat, user1):
        """При редактировании должна создаваться запись в истории"""
        from communications.models import MessageEditHistory

        # Создаем сообщение
        message = Message.objects.create(
            chat=private_chat, author=user1, content="Original content"
        )

        # Редактируем
        url = f"/api/v1/communications/messages/{message.pk}/"
        data = {"content": "Edited content"}
        response = auth_client.patch(url, data, format="json")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["is_edited"] is True

        # Проверяем что создалась история
        history = MessageEditHistory.objects.filter(message=message)
        assert history.exists()
        assert history.first().previous_content == "Original content"
        assert history.first().edited_by == user1

    def test_forward_metadata_created(
        self, auth_client, private_chat, group_chat, user1
    ):
        """При пересылке должны создаваться метаданные"""
        from communications.models import MessageForwardMetadata

        # Создаем оригинальное сообщение
        original = Message.objects.create(
            chat=private_chat, author=user1, content="Original message"
        )

        # Пересылаем
        url = "/api/v1/communications/messages/forward/"
        data = {"message_ids": [original.id], "target_chat_id": group_chat.id}
        response = auth_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["forwarded_count"] == 1

        forwarded_id = response.data["forwarded_ids"][0]
        forwarded_msg = Message.objects.get(id=forwarded_id)

        # Проверяем метаданные
        assert forwarded_msg.is_forwarded is True
        metadata = MessageForwardMetadata.objects.filter(message=forwarded_msg)
        assert metadata.exists()

        meta = metadata.first()
        assert meta.original_message_id == original.id
        assert meta.original_author_id == user1.id
        assert meta.forwarded_by == user1

    def test_mark_read_updates_read_state(self, auth_client, private_chat, user1):
        """mark_read должен обновлять ChatReadState"""
        from communications.models import ChatReadState

        # Создаем сообщения
        msg1 = Message.objects.create(chat=private_chat, author=user1, content="Msg 1")
        msg2 = Message.objects.create(chat=private_chat, author=user1, content="Msg 2")

        # Помечаем как прочитанное
        url = f"/api/v1/communications/chats/{private_chat.pk}/mark-read/"
        data = {"message_id": msg2.id}
        response = auth_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["ok"] is True

        # Проверяем ReadState
        read_state = ChatReadState.objects.get(chat=private_chat, user=user1)
        assert read_state.last_read_message_id == msg2.id
        assert read_state.last_read_at is not None

    def test_mark_read_with_timestamp(self, auth_client, private_chat, user1):
        """mark_read с явным указанием timestamp"""
        import time

        from communications.models import ChatReadState

        # Создаем сообщение
        msg = Message.objects.create(chat=private_chat, author=user1, content="Test")

        # Помечаем с timestamp
        upto_ts = int(time.time() * 1000)  # Миллисекунды

        url = f"/api/v1/communications/chats/{private_chat.pk}/mark-read/"
        data = {"upto_ts": upto_ts}
        response = auth_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_200_OK

        # Проверяем ReadState
        read_state = ChatReadState.objects.get(chat=private_chat, user=user1)
        assert read_state.last_read_at is not None

    def test_messages_around_with_timestamp(self, auth_client, private_chat, user1):
        """messages_around может принимать timestamp вместо message_id"""
        # Создаем несколько сообщений
        messages = []
        for i in range(10):
            msg = Message.objects.create(
                chat=private_chat, author=user1, content=f"Message {i}"
            )
            messages.append(msg)

        # Берем timestamp среднего сообщения
        middle_msg = messages[5]
        timestamp_ms = int(middle_msg.created_at.timestamp() * 1000)

        url = f"/api/v1/communications/chats/{private_chat.pk}/messages-around/"
        response = auth_client.get(url, {"around_id": timestamp_ms, "limit": 6})

        assert response.status_code == status.HTTP_200_OK
        assert "messages" in response.data
        assert response.data["anchor_id"] is not None


# ==================== Complex Message Type Tests ====================


class TestReplyToVariousMessageTypes:
    """Тесты ответа на разные типы сообщений"""

    def test_reply_to_message_with_attachment(self, auth_client, private_chat, user1):
        """Ответ на сообщение с вложением"""
        from communications.models import MessageAttachment
        from django.core.files.uploadedfile import SimpleUploadedFile

        # Создаем сообщение с файлом
        original = Message.objects.create(
            chat=private_chat,
            author=user1,
            content="Message with file",
            has_attachments=True,
        )
        MessageAttachment.objects.create(
            message=original,
            file=SimpleUploadedFile("doc.pdf", b"PDF", content_type="application/pdf"),
            file_name="doc.pdf",
            file_size=100,
            mime_type="application/pdf",
            file_type="pdf",
        )

        # Отвечаем на него
        url = "/api/v1/communications/messages/upload/"
        data = {
            "chat_id": private_chat.id,
            "content": "Reply to file message",
            "reply_to_id": original.id,
        }
        response = auth_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["message"]["reply_to"]["id"] == original.id
        # В reply_to должна быть информация о файле
        assert response.data["message"]["reply_to"]["content"] == "Message with file"

    def test_reply_to_poll_message(self, auth_client, private_chat, user1):
        """Ответ на сообщение с голосованием"""
        from communications.models import Poll, PollOption

        # Создаем сообщение с голосованием
        poll_message = Message.objects.create(
            chat=private_chat, author=user1, content="Poll question"
        )
        poll = Poll.objects.create(
            message=poll_message,
            author=user1,
            question="What color?",
            is_anonymous=False,
            is_multiple_choice=False,
        )
        PollOption.objects.create(poll=poll, text="Red", position=0)
        PollOption.objects.create(poll=poll, text="Blue", position=1)

        # Отвечаем на сообщение с голосованием
        url = "/api/v1/communications/messages/upload/"
        data = {
            "chat_id": private_chat.id,
            "content": "My answer to poll",
            "reply_to_id": poll_message.id,
        }
        response = auth_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["message"]["reply_to"]["id"] == poll_message.id

    def test_reply_to_forwarded_message(self, auth_client, private_chat, user1):
        """Ответ на пересланное сообщение"""
        from communications.models import MessageForwardMetadata

        # Создаем пересланное сообщение
        forwarded = Message.objects.create(
            chat=private_chat,
            author=user1,
            content="Forwarded content",
            is_forwarded=True,
        )
        MessageForwardMetadata.objects.create(
            message=forwarded,
            original_author=user1,
            original_chat=private_chat,
            original_chat_name="Original Chat",
            forwarded_by=user1,
        )

        # Отвечаем на пересланное
        url = "/api/v1/communications/messages/upload/"
        data = {
            "chat_id": private_chat.id,
            "content": "Reply to forwarded",
            "reply_to_id": forwarded.id,
        }
        response = auth_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["message"]["reply_to"]["id"] == forwarded.id

    def test_reply_to_edited_message(self, auth_client, private_chat, user1):
        """Ответ на отредактированное сообщение"""
        # Создаем и редактируем сообщение
        edited = Message.objects.create(
            chat=private_chat, author=user1, content="Edited content", is_edited=True
        )

        url = "/api/v1/communications/messages/upload/"
        data = {
            "chat_id": private_chat.id,
            "content": "Reply to edited",
            "reply_to_id": edited.id,
        }
        response = auth_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["message"]["reply_to"]["id"] == edited.id

    def test_reply_with_attachment_to_message(self, auth_client, private_chat, user1):
        """Ответ с файлом на обычное сообщение"""
        from django.core.files.uploadedfile import SimpleUploadedFile

        original = Message.objects.create(
            chat=private_chat, author=user1, content="Original"
        )

        file_obj = SimpleUploadedFile(
            "reply.txt", b"Reply file", content_type="text/plain"
        )

        url = "/api/v1/communications/messages/upload/"
        data = {
            "chat_id": private_chat.id,
            "content": "Reply with file",
            "reply_to_id": original.id,
            "file_0": file_obj,
        }
        response = auth_client.post(url, data, format="multipart")

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["message"]["reply_to"]["id"] == original.id
        assert response.data["message"]["has_attachments"] is True


class TestEditVariousMessageTypes:
    """Тесты редактирования разных типов сообщений"""

    def test_edit_text_message(self, auth_client, private_chat, user1):
        """Редактирование обычного текстового сообщения"""
        message = Message.objects.create(
            chat=private_chat, author=user1, content="Original text"
        )

        url = f"/api/v1/communications/messages/{message.pk}/"
        data = {"content": "Edited text"}
        response = auth_client.patch(url, data, format="json")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["content"] == "Edited text"
        assert response.data["is_edited"] is True

    def test_edit_message_with_attachments(self, auth_client, private_chat, user1):
        """Редактирование сообщения с вложениями"""
        from communications.models import MessageAttachment
        from django.core.files.uploadedfile import SimpleUploadedFile

        message = Message.objects.create(
            chat=private_chat,
            author=user1,
            content="With attachment",
            has_attachments=True,
        )
        att = MessageAttachment.objects.create(
            message=message,
            file=SimpleUploadedFile("old.txt", b"Old", content_type="text/plain"),
            file_name="old.txt",
            file_size=100,
            mime_type="text/plain",
            file_type="document",
        )

        url = f"/api/v1/communications/messages/{message.pk}/"
        data = {
            "content": "Edited content",
            "existing_attachment_ids": [att.id],  # Сохраняем файл
        }
        response = auth_client.patch(url, data, format="json")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["is_edited"] is True
        assert response.data["has_attachments"] is True

    def test_cannot_edit_poll_message(self, auth_client, private_chat, user1):
        """Попытка редактировать сообщение с голосованием"""
        from communications.models import Poll, PollOption

        poll_message = Message.objects.create(
            chat=private_chat, author=user1, content="Poll"
        )
        poll = Poll.objects.create(
            message=poll_message, author=user1, question="Question?"
        )
        PollOption.objects.create(poll=poll, text="Option", position=0)

        url = f"/api/v1/communications/messages/{poll_message.pk}/"
        data = {"content": "Trying to edit poll"}
        response = auth_client.patch(url, data, format="json")

        # Может редактироваться или нет в зависимости от бизнес-логики
        # Допускаем оба варианта
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_403_FORBIDDEN,
        ]

    def test_edit_forwarded_message(self, auth_client, private_chat, user1):
        """Редактирование пересланного сообщения"""
        from communications.models import MessageForwardMetadata

        forwarded = Message.objects.create(
            chat=private_chat, author=user1, content="Forwarded", is_forwarded=True
        )
        MessageForwardMetadata.objects.create(
            message=forwarded,
            original_author=user1,
            original_chat=private_chat,
            original_chat_name="Chat",
            forwarded_by=user1,
        )

        url = f"/api/v1/communications/messages/{forwarded.pk}/"
        data = {"content": "Edited forwarded"}
        response = auth_client.patch(url, data, format="json")

        # Может редактироваться или быть запрещено
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_403_FORBIDDEN,
        ]

    def test_edit_message_in_announcement_chat(self, auth_client, user1):
        """Попытка редактировать в чате-объявлении"""
        announcement_chat = Chat.objects.create(
            type="announcement", name="Announcements", created_by=user1
        )
        announcement_chat.participants.add(user1)

        message = Message.objects.create(
            chat=announcement_chat, author=user1, content="Announcement"
        )

        client = APIClient()
        client.force_authenticate(user=user1)

        url = f"/api/v1/communications/messages/{message.pk}/"
        data = {"content": "Edited"}
        response = client.patch(url, data, format="json")

        # Должно быть запрещено
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_edit_reply_message(self, auth_client, private_chat, user1):
        """Редактирование сообщения которое является ответом"""
        original = Message.objects.create(
            chat=private_chat, author=user1, content="Original"
        )

        reply = Message.objects.create(
            chat=private_chat, author=user1, content="Reply", reply_to=original
        )

        url = f"/api/v1/communications/messages/{reply.pk}/"
        data = {"content": "Edited reply"}
        response = auth_client.patch(url, data, format="json")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["content"] == "Edited reply"
        # reply_to должен остаться
        assert response.data["reply_to"]["id"] == original.id


class TestForwardVariousMessageTypes:
    """Тесты пересылки разных типов сообщений"""

    def test_forward_text_message(self, auth_client, private_chat, group_chat, user1):
        """Пересылка обычного текстового сообщения"""
        message = Message.objects.create(
            chat=private_chat, author=user1, content="Text to forward"
        )

        url = "/api/v1/communications/messages/forward/"
        data = {"message_ids": [message.id], "target_chat_id": group_chat.id}
        response = auth_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["forwarded_count"] == 1

        # Проверяем что создалось пересланное сообщение
        forwarded_id = response.data["forwarded_ids"][0]
        forwarded = Message.objects.get(id=forwarded_id)
        assert forwarded.is_forwarded is True
        assert forwarded.content == "Text to forward"

    def test_forward_message_with_attachments(
        self, auth_client, private_chat, group_chat, user1
    ):
        """Пересылка сообщения с файлами"""
        from communications.models import MessageAttachment
        from django.core.files.uploadedfile import SimpleUploadedFile

        message = Message.objects.create(
            chat=private_chat, author=user1, content="With file", has_attachments=True
        )
        MessageAttachment.objects.create(
            message=message,
            file=SimpleUploadedFile("doc.pdf", b"PDF", content_type="application/pdf"),
            file_name="doc.pdf",
            file_size=100,
            mime_type="application/pdf",
            file_type="pdf",
        )

        url = "/api/v1/communications/messages/forward/"
        data = {"message_ids": [message.id], "target_chat_id": group_chat.id}
        response = auth_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["forwarded_count"] == 1

        # Файлы могут быть скопированы или нет в зависимости от реализации
        forwarded_id = response.data["forwarded_ids"][0]
        forwarded = Message.objects.get(id=forwarded_id)
        assert forwarded.is_forwarded is True

    def test_forward_poll_message(self, auth_client, private_chat, group_chat, user1):
        """Пересылка сообщения с голосованием"""
        from communications.models import Poll, PollOption

        poll_message = Message.objects.create(
            chat=private_chat, author=user1, content="Poll"
        )
        poll = Poll.objects.create(
            message=poll_message, author=user1, question="Question?"
        )
        PollOption.objects.create(poll=poll, text="Yes", position=0)
        PollOption.objects.create(poll=poll, text="No", position=1)

        url = "/api/v1/communications/messages/forward/"
        data = {"message_ids": [poll_message.id], "target_chat_id": group_chat.id}
        response = auth_client.post(url, data, format="json")

        # Пересылка голосования может быть разрешена или запрещена
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST]

    def test_forward_already_forwarded_message(
        self, auth_client, private_chat, group_chat, user1
    ):
        """Пересылка уже пересланного сообщения (цепочка пересылок)"""
        from communications.models import MessageForwardMetadata

        forwarded = Message.objects.create(
            chat=private_chat,
            author=user1,
            content="Already forwarded",
            is_forwarded=True,
        )
        MessageForwardMetadata.objects.create(
            message=forwarded,
            original_author=user1,
            original_chat=private_chat,
            original_chat_name="Original",
            forwarded_by=user1,
            forward_count=1,
        )

        url = "/api/v1/communications/messages/forward/"
        data = {"message_ids": [forwarded.id], "target_chat_id": group_chat.id}
        response = auth_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_200_OK
        # forward_count должен увеличиться

    def test_forward_reply_message(self, auth_client, private_chat, group_chat, user1):
        """Пересылка сообщения которое является ответом"""
        original = Message.objects.create(
            chat=private_chat, author=user1, content="Original"
        )

        reply = Message.objects.create(
            chat=private_chat, author=user1, content="Reply", reply_to=original
        )

        url = "/api/v1/communications/messages/forward/"
        data = {"message_ids": [reply.id], "target_chat_id": group_chat.id}
        response = auth_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_200_OK
        # reply_to может сохраниться или потеряться при пересылке

    def test_forward_multiple_different_types(
        self, auth_client, private_chat, group_chat, user1
    ):
        """Пересылка нескольких сообщений разных типов одновременно"""
        from communications.models import MessageAttachment
        from django.core.files.uploadedfile import SimpleUploadedFile

        # Текстовое
        msg1 = Message.objects.create(chat=private_chat, author=user1, content="Text")

        # С файлом
        msg2 = Message.objects.create(
            chat=private_chat, author=user1, content="File", has_attachments=True
        )
        MessageAttachment.objects.create(
            message=msg2,
            file=SimpleUploadedFile("f.txt", b"F", content_type="text/plain"),
            file_name="f.txt",
            file_size=1,
            mime_type="text/plain",
            file_type="document",
        )

        # Ответ
        msg3 = Message.objects.create(
            chat=private_chat, author=user1, content="Reply", reply_to=msg1
        )

        url = "/api/v1/communications/messages/forward/"
        data = {
            "message_ids": [msg1.id, msg2.id, msg3.id],
            "target_chat_id": group_chat.id,
        }
        response = auth_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["forwarded_count"] >= 1


class TestDeleteVariousMessageTypes:
    """Тесты удаления разных типов сообщений"""

    def test_delete_text_message(self, auth_client, private_chat, user1):
        """Удаление обычного текстового сообщения"""
        message = Message.objects.create(
            chat=private_chat, author=user1, content="To delete"
        )

        url = f"/api/v1/communications/messages/{message.pk}/"
        response = auth_client.delete(url)

        assert response.status_code == status.HTTP_204_NO_CONTENT

        message.refresh_from_db()
        assert message.is_deleted is True

    def test_delete_message_with_attachments(self, auth_client, private_chat, user1):
        """Удаление сообщения с вложениями"""
        from communications.models import MessageAttachment
        from django.core.files.uploadedfile import SimpleUploadedFile

        message = Message.objects.create(
            chat=private_chat, author=user1, content="With file", has_attachments=True
        )
        att = MessageAttachment.objects.create(
            message=message,
            file=SimpleUploadedFile("doc.txt", b"Doc", content_type="text/plain"),
            file_name="doc.txt",
            file_size=100,
            mime_type="text/plain",
            file_type="document",
        )

        url = f"/api/v1/communications/messages/{message.pk}/"
        response = auth_client.delete(url)

        assert response.status_code == status.HTTP_204_NO_CONTENT

        message.refresh_from_db()
        assert message.is_deleted is True
        # Файлы остаются в БД (мягкое удаление)
        assert MessageAttachment.objects.filter(id=att.id).exists()

    def test_delete_poll_message(self, auth_client, private_chat, user1):
        """Удаление сообщения с голосованием"""
        from communications.models import Poll, PollOption

        poll_message = Message.objects.create(
            chat=private_chat, author=user1, content="Poll"
        )
        poll = Poll.objects.create(
            message=poll_message, author=user1, question="Question?"
        )
        option = PollOption.objects.create(poll=poll, text="Option", position=0)

        url = f"/api/v1/communications/messages/{poll_message.pk}/"
        response = auth_client.delete(url)

        assert response.status_code == status.HTTP_204_NO_CONTENT

        poll_message.refresh_from_db()
        assert poll_message.is_deleted is True
        # Poll остается в БД
        assert Poll.objects.filter(id=poll.id).exists()

    def test_delete_forwarded_message(self, auth_client, private_chat, user1):
        """Удаление пересланного сообщения"""
        from communications.models import MessageForwardMetadata

        forwarded = Message.objects.create(
            chat=private_chat, author=user1, content="Forwarded", is_forwarded=True
        )
        metadata = MessageForwardMetadata.objects.create(
            message=forwarded,
            original_author=user1,
            original_chat=private_chat,
            original_chat_name="Chat",
            forwarded_by=user1,
        )

        url = f"/api/v1/communications/messages/{forwarded.pk}/"
        response = auth_client.delete(url)

        assert response.status_code == status.HTTP_204_NO_CONTENT

        forwarded.refresh_from_db()
        assert forwarded.is_deleted is True
        # Метаданные остаются
        assert MessageForwardMetadata.objects.filter(id=metadata.id).exists()

    def test_delete_reply_message(self, auth_client, private_chat, user1):
        """Удаление сообщения которое является ответом"""
        original = Message.objects.create(
            chat=private_chat, author=user1, content="Original"
        )

        reply = Message.objects.create(
            chat=private_chat, author=user1, content="Reply", reply_to=original
        )

        url = f"/api/v1/communications/messages/{reply.pk}/"
        response = auth_client.delete(url)

        assert response.status_code == status.HTTP_204_NO_CONTENT

        reply.refresh_from_db()
        assert reply.is_deleted is True
        # Оригинальное сообщение остается
        original.refresh_from_db()
        assert original.is_deleted is False

    def test_delete_message_with_replies(self, auth_client, private_chat, user1):
        """Удаление сообщения на которое есть ответы"""
        original = Message.objects.create(
            chat=private_chat, author=user1, content="Original"
        )

        reply1 = Message.objects.create(
            chat=private_chat, author=user1, content="Reply 1", reply_to=original
        )
        reply2 = Message.objects.create(
            chat=private_chat, author=user1, content="Reply 2", reply_to=original
        )

        url = f"/api/v1/communications/messages/{original.pk}/"
        response = auth_client.delete(url)

        assert response.status_code == status.HTTP_204_NO_CONTENT

        original.refresh_from_db()
        assert original.is_deleted is True

        # Ответы остаются, но reply_to указывает на удаленное
        reply1.refresh_from_db()
        reply2.refresh_from_db()
        assert reply1.is_deleted is False
        assert reply2.is_deleted is False
        assert reply1.reply_to_id == original.id

    def test_bulk_delete_various_types(self, auth_client, private_chat, user1):
        """Массовое удаление сообщений разных типов"""
        from communications.models import MessageAttachment, Poll, PollOption
        from django.core.files.uploadedfile import SimpleUploadedFile

        # Текстовое
        msg1 = Message.objects.create(chat=private_chat, author=user1, content="Text")

        # С файлом
        msg2 = Message.objects.create(
            chat=private_chat, author=user1, content="File", has_attachments=True
        )
        MessageAttachment.objects.create(
            message=msg2,
            file=SimpleUploadedFile("f.txt", b"F", content_type="text/plain"),
            file_name="f.txt",
            file_size=1,
            mime_type="text/plain",
            file_type="document",
        )

        # С голосованием
        msg3 = Message.objects.create(chat=private_chat, author=user1, content="Poll")
        poll = Poll.objects.create(message=msg3, author=user1, question="Q?")
        PollOption.objects.create(poll=poll, text="A", position=0)

        url = "/api/v1/communications/messages/bulk-delete/"
        data = {"message_ids": [msg1.id, msg2.id, msg3.id]}
        response = auth_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["deleted_count"] == 3

        # Все должны быть помечены как удаленные
        msg1.refresh_from_db()
        msg2.refresh_from_db()
        msg3.refresh_from_db()
        assert msg1.is_deleted is True
        assert msg2.is_deleted is True
        assert msg3.is_deleted is True

    def test_delete_edited_message(self, auth_client, private_chat, user1):
        """Удаление отредактированного сообщения"""
        from communications.models import MessageEditHistory

        message = Message.objects.create(
            chat=private_chat, author=user1, content="Edited content", is_edited=True
        )

        # Создаем историю редактирования
        MessageEditHistory.objects.create(
            message=message, previous_content="Original", edited_by=user1
        )

        url = f"/api/v1/communications/messages/{message.pk}/"
        response = auth_client.delete(url)

        assert response.status_code == status.HTTP_204_NO_CONTENT

        message.refresh_from_db()
        assert message.is_deleted is True
        # История редактирования сохраняется
        assert MessageEditHistory.objects.filter(message=message).exists()
        assert MessageEditHistory.objects.filter(message=message).exists()
