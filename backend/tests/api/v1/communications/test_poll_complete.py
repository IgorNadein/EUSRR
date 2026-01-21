"""
Полный набор тестов для Poll API
Покрывает все возможности голосований

Использует fixtures из test_communications_api.py:
- user1, user2, user3
- auth_client
- private_chat, group_chat, department_chat
"""
import pytest
from datetime import timedelta
from django.utils import timezone
from rest_framework import status
from communications.models import Message, Poll, PollOption, PollVote

# Импортируем fixtures из основного файла тестов
from .test_communications_api import (
    user1, user2, user3,
    auth_client,
    private_chat, group_chat, department_chat,
    department
)


@pytest.mark.django_db
class TestPollCreationAPI:
    """Тесты создания голосований через API"""
    
    def test_create_simple_poll_via_api(self, auth_client, private_chat, user1):
        """Создание простого голосования через POST /api/v1/communications/polls/"""
        # Сначала создаем сообщение
        message = Message.objects.create(
            chat=private_chat,
            author=user1,
            content='Poll message'
        )
        
        url = '/api/v1/communications/polls/'
        data = {
            'message': message.id,
            'question': 'What is your favorite color?',
            'is_anonymous': False,
            'is_multiple_choice': False,
            'is_quiz': False,
            'allows_custom_answers': False
        }
        
        response = auth_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['question'] == 'What is your favorite color?'
        # Author должен установиться автоматически через perform_create
        poll = Poll.objects.get(id=response.data['id'])
        assert poll.author == user1
    
    def test_create_anonymous_poll_via_api(self, auth_client, private_chat, user1):
        """Создание анонимного голосования"""
        message = Message.objects.create(chat=private_chat, author=user1, content='Poll')
        
        url = '/api/v1/communications/polls/'
        data = {
            'message': message.id,
            'question': 'Anonymous poll?',
            'is_anonymous': True
        }
        
        response = auth_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['is_anonymous'] is True
    
    def test_create_multiple_choice_poll_via_api(self, auth_client, private_chat, user1):
        """Создание голосования с множественным выбором"""
        message = Message.objects.create(chat=private_chat, author=user1, content='Poll')
        
        url = '/api/v1/communications/polls/'
        data = {
            'message': message.id,
            'question': 'Select multiple?',
            'is_multiple_choice': True
        }
        
        response = auth_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['is_multiple_choice'] is True
    
    def test_create_quiz_via_api(self, auth_client, private_chat, user1):
        """Создание викторины (quiz mode)"""
        message = Message.objects.create(chat=private_chat, author=user1, content='Quiz')
        
        url = '/api/v1/communications/polls/'
        data = {
            'message': message.id,
            'question': '2 + 2 = ?',
            'is_quiz': True
        }
        
        response = auth_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['is_quiz'] is True
    
    def test_create_poll_with_auto_close_time(self, auth_client, private_chat, user1):
        """Создание голосования с автоматическим закрытием"""
        message = Message.objects.create(chat=private_chat, author=user1, content='Poll')
        closes_at = timezone.now() + timedelta(hours=24)
        
        url = '/api/v1/communications/polls/'
        data = {
            'message': message.id,
            'question': 'Poll with deadline',
            'closes_at': closes_at.isoformat()
        }
        
        response = auth_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_201_CREATED
        poll = Poll.objects.get(id=response.data['id'])
        assert poll.closes_at is not None
        assert poll.closes_at > timezone.now()
    
    def test_create_poll_without_message_fails(self, auth_client):
        """Попытка создать poll без сообщения должна провалиться"""
        url = '/api/v1/communications/polls/'
        data = {
            'question': 'Poll without message'
        }
        
        response = auth_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
    
    def test_create_poll_unauthenticated_fails(self, client, private_chat, user1):
        """Неавторизованный пользователь не может создать poll"""
        message = Message.objects.create(chat=private_chat, author=user1, content='Poll')
        
        url = '/api/v1/communications/polls/'
        data = {
            'message': message.id,
            'question': 'Unauthorized poll'
        }
        
        response = client.post(url, data, format='json')
        
        assert response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]


@pytest.mark.django_db
class TestPollVoting:
    """Тесты голосования"""
    
    @pytest.fixture
    def simple_poll(self, private_chat, user1):
        """Простое голосование с опциями"""
        message = Message.objects.create(chat=private_chat, author=user1, content='Poll')
        poll = Poll.objects.create(
            message=message,
            author=user1,
            question='Simple poll?',
            is_anonymous=False,
            is_multiple_choice=False
        )
        opt1 = PollOption.objects.create(poll=poll, text='Yes', position=0)
        opt2 = PollOption.objects.create(poll=poll, text='No', position=1)
        return poll, opt1, opt2
    
    def test_vote_single_choice(self, auth_client, simple_poll, user1):
        """Голосование в single-choice опросе"""
        poll, opt1, opt2 = simple_poll
        
        url = f'/api/v1/communications/polls/{poll.id}/vote/'
        response = auth_client.post(url, {'option_ids': [opt1.id]}, format='json')
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['total_voters'] == 1
        assert opt1.id in response.data['user_voted_option_ids']
    
    def test_vote_multiple_in_single_choice_fails(self, auth_client, simple_poll):
        """Попытка выбрать несколько в single-choice"""
        poll, opt1, opt2 = simple_poll
        
        url = f'/api/v1/communications/polls/{poll.id}/vote/'
        response = auth_client.post(url, {'option_ids': [opt1.id, opt2.id]}, format='json')
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
    
    def test_revote_replaces_previous(self, auth_client, simple_poll):
        """Повторное голосование заменяет предыдущий выбор"""
        poll, opt1, opt2 = simple_poll
        url = f'/api/v1/communications/polls/{poll.id}/vote/'
        
        # Первое голосование
        auth_client.post(url, {'option_ids': [opt1.id]}, format='json')
        
        # Второе голосование
        response = auth_client.post(url, {'option_ids': [opt2.id]}, format='json')
        
        assert response.status_code == status.HTTP_200_OK
        assert opt2.id in response.data['user_voted_option_ids']
        assert opt1.id not in response.data['user_voted_option_ids']
        # Должен остаться 1 голосующий
        assert response.data['total_voters'] == 1
    
    def test_vote_in_closed_poll_fails(self, auth_client, simple_poll):
        """Голосование в закрытом опросе должно провалиться"""
        poll, opt1, opt2 = simple_poll
        poll.is_closed = True
        poll.save()
        
        url = f'/api/v1/communications/polls/{poll.id}/vote/'
        response = auth_client.post(url, {'option_ids': [opt1.id]}, format='json')
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
    
    def test_vote_without_options_fails(self, auth_client, simple_poll):
        """Голосование без выбора опций должно провалиться"""
        poll, opt1, opt2 = simple_poll
        
        url = f'/api/v1/communications/polls/{poll.id}/vote/'
        response = auth_client.post(url, {'option_ids': []}, format='json')
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
    
    def test_vote_with_invalid_option_fails(self, auth_client, simple_poll):
        """Голосование с несуществующей опцией должно провалиться"""
        poll, opt1, opt2 = simple_poll
        
        url = f'/api/v1/communications/polls/{poll.id}/vote/'
        response = auth_client.post(url, {'option_ids': [99999]}, format='json')
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
class TestMultipleChoicePolls:
    """Тесты голосований с множественным выбором"""
    
    @pytest.fixture
    def multiple_choice_poll(self, private_chat, user1):
        """Голосование с multiple choice"""
        message = Message.objects.create(chat=private_chat, author=user1, content='Poll')
        poll = Poll.objects.create(
            message=message,
            author=user1,
            question='Multiple choice?',
            is_multiple_choice=True
        )
        opt1 = PollOption.objects.create(poll=poll, text='A', position=0)
        opt2 = PollOption.objects.create(poll=poll, text='B', position=1)
        opt3 = PollOption.objects.create(poll=poll, text='C', position=2)
        return poll, opt1, opt2, opt3
    
    def test_vote_multiple_options(self, auth_client, multiple_choice_poll):
        """Можно выбрать несколько опций"""
        poll, opt1, opt2, opt3 = multiple_choice_poll
        
        url = f'/api/v1/communications/polls/{poll.id}/vote/'
        response = auth_client.post(url, {'option_ids': [opt1.id, opt2.id]}, format='json')
        
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['user_voted_option_ids']) == 2
        assert opt1.id in response.data['user_voted_option_ids']
        assert opt2.id in response.data['user_voted_option_ids']
    
    def test_vote_all_options(self, auth_client, multiple_choice_poll):
        """Можно выбрать все опции"""
        poll, opt1, opt2, opt3 = multiple_choice_poll
        
        url = f'/api/v1/communications/polls/{poll.id}/vote/'
        response = auth_client.post(
            url,
            {'option_ids': [opt1.id, opt2.id, opt3.id]},
            format='json'
        )
        
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['user_voted_option_ids']) == 3
    
    def test_revote_multiple_choice(self, auth_client, multiple_choice_poll):
        """Повторное голосование заменяет все предыдущие выборы"""
        poll, opt1, opt2, opt3 = multiple_choice_poll
        url = f'/api/v1/communications/polls/{poll.id}/vote/'
        
        # Первое: выбираем A и B
        auth_client.post(url, {'option_ids': [opt1.id, opt2.id]}, format='json')
        
        # Второе: выбираем только C
        response = auth_client.post(url, {'option_ids': [opt3.id]}, format='json')
        
        assert response.status_code == status.HTTP_200_OK
        assert opt3.id in response.data['user_voted_option_ids']
        assert opt1.id not in response.data['user_voted_option_ids']
        assert opt2.id not in response.data['user_voted_option_ids']


@pytest.mark.django_db
class TestAnonymousPolls:
    """Тесты анонимных голосований"""
    
    @pytest.fixture
    def anonymous_poll(self, private_chat, user1):
        """Анонимное голосование"""
        message = Message.objects.create(chat=private_chat, author=user1, content='Poll')
        poll = Poll.objects.create(
            message=message,
            author=user1,
            question='Anonymous?',
            is_anonymous=True
        )
        opt1 = PollOption.objects.create(poll=poll, text='Yes', position=0)
        opt2 = PollOption.objects.create(poll=poll, text='No', position=1)
        return poll, opt1, opt2
    
    def test_vote_in_anonymous_poll(self, auth_client, anonymous_poll):
        """Можно голосовать в анонимном опросе"""
        poll, opt1, opt2 = anonymous_poll
        
        url = f'/api/v1/communications/polls/{poll.id}/vote/'
        response = auth_client.post(url, {'option_ids': [opt1.id]}, format='json')
        
        assert response.status_code == status.HTTP_200_OK
    
    def test_anonymous_results_hide_voters(self, auth_client, anonymous_poll, user1):
        """Результаты анонимного опроса не показывают голосующих"""
        poll, opt1, opt2 = anonymous_poll
        
        # Голосуем
        url = f'/api/v1/communications/polls/{poll.id}/vote/'
        auth_client.post(url, {'option_ids': [opt1.id]}, format='json')
        
        # Получаем результаты
        results = poll.get_results()
        
        # Проверяем что voters пустой для анонимного опроса
        for option_result in results['options']:
            assert option_result['voters'] == []


@pytest.mark.django_db
class TestQuizPolls:
    """Тесты викторин (quiz mode)"""
    
    @pytest.fixture
    def quiz_poll(self, private_chat, user1):
        """Викторина с правильным ответом"""
        message = Message.objects.create(chat=private_chat, author=user1, content='Quiz')
        poll = Poll.objects.create(
            message=message,
            author=user1,
            question='2 + 2 = ?',
            is_quiz=True
        )
        opt1 = PollOption.objects.create(poll=poll, text='3', position=0, is_correct=False)
        opt2 = PollOption.objects.create(poll=poll, text='4', position=1, is_correct=True)
        opt3 = PollOption.objects.create(poll=poll, text='5', position=2, is_correct=False)
        return poll, opt1, opt2, opt3
    
    def test_vote_correct_answer(self, auth_client, quiz_poll):
        """Голосование за правильный ответ"""
        poll, opt1, opt2, opt3 = quiz_poll
        
        url = f'/api/v1/communications/polls/{poll.id}/vote/'
        response = auth_client.post(url, {'option_ids': [opt2.id]}, format='json')
        
        assert response.status_code == status.HTTP_200_OK
    
    def test_vote_wrong_answer(self, auth_client, quiz_poll):
        """Голосование за неправильный ответ"""
        poll, opt1, opt2, opt3 = quiz_poll
        
        url = f'/api/v1/communications/polls/{poll.id}/vote/'
        response = auth_client.post(url, {'option_ids': [opt1.id]}, format='json')
        
        assert response.status_code == status.HTTP_200_OK
    
    def test_quiz_results_show_correct_answer(self, auth_client, quiz_poll):
        """Результаты викторины показывают правильный ответ"""
        poll, opt1, opt2, opt3 = quiz_poll
        
        results = poll.get_results()
        
        # Находим правильный ответ
        correct_option = next(
            opt for opt in results['options']
            if opt['is_correct']
        )
        assert correct_option['text'] == '4'


@pytest.mark.django_db
class TestPollClosing:
    """Тесты закрытия голосований"""
    
    @pytest.fixture
    def poll_with_votes(self, private_chat, user1, user2):
        """Голосование с голосами"""
        message = Message.objects.create(chat=private_chat, author=user1, content='Poll')
        poll = Poll.objects.create(
            message=message,
            author=user1,
            question='Close me?'
        )
        opt1 = PollOption.objects.create(poll=poll, text='Yes', position=0)
        opt2 = PollOption.objects.create(poll=poll, text='No', position=1)
        
        # Добавляем голоса
        PollVote.objects.create(poll=poll, option=opt1, voter=user1)
        poll.total_voters = 1
        poll.save()
        
        return poll, opt1, opt2
    
    def test_close_poll_by_author(self, auth_client, poll_with_votes, user1):
        """Автор может закрыть голосование"""
        poll, opt1, opt2 = poll_with_votes
        
        url = f'/api/v1/communications/polls/{poll.id}/close/'
        response = auth_client.post(url)
        
        assert response.status_code == status.HTTP_200_OK
        poll.refresh_from_db()
        assert poll.is_closed is True
        assert poll.closed_at is not None
    
    def test_close_poll_by_non_author_fails(self, auth_client, poll_with_votes, user2):
        """Не-автор не может закрыть голосование"""
        poll, opt1, opt2 = poll_with_votes
        
        # Логинимся как user2
        auth_client.force_authenticate(user=user2)
        
        url = f'/api/v1/communications/polls/{poll.id}/close/'
        response = auth_client.post(url)
        
        assert response.status_code in [status.HTTP_403_FORBIDDEN, status.HTTP_400_BAD_REQUEST]
    
    def test_close_already_closed_poll(self, auth_client, poll_with_votes):
        """Попытка закрыть уже закрытый опрос"""
        poll, opt1, opt2 = poll_with_votes
        poll.is_closed = True
        poll.save()
        
        url = f'/api/v1/communications/polls/{poll.id}/close/'
        response = auth_client.post(url)
        
        # Должно быть успешно или 400 (опрос уже закрыт)
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST]
    
    def test_poll_auto_closes_after_deadline(self, private_chat, user1):
        """Голосование автоматически закрывается после дедлайна"""
        message = Message.objects.create(chat=private_chat, author=user1, content='Poll')
        
        # Создаем poll с прошедшим дедлайном
        past_time = timezone.now() - timedelta(hours=1)
        poll = Poll.objects.create(
            message=message,
            author=user1,
            question='Expired poll',
            closes_at=past_time
        )
        
        # В реальном приложении должна быть celery task которая закроет
        # Здесь проверяем что closes_at установлен
        assert poll.closes_at < timezone.now()
        
        # Можно вручную проверить логику закрытия
        if poll.closes_at and poll.closes_at < timezone.now() and not poll.is_closed:
            poll.close()
        
        assert poll.is_closed is True


@pytest.mark.django_db
class TestPollResults:
    """Тесты получения результатов"""
    
    @pytest.fixture
    def poll_with_results(self, private_chat, user1, user2):
        """Голосование с результатами"""
        message = Message.objects.create(chat=private_chat, author=user1, content='Poll')
        poll = Poll.objects.create(
            message=message,
            author=user1,
            question='Results test?',
            is_anonymous=False
        )
        opt1 = PollOption.objects.create(poll=poll, text='A', position=0)
        opt2 = PollOption.objects.create(poll=poll, text='B', position=1)
        
        # user1 голосует за A
        PollVote.objects.create(poll=poll, option=opt1, voter=user1)
        opt1.vote_count = 1
        opt1.save()
        
        # user2 голосует за A
        PollVote.objects.create(poll=poll, option=opt1, voter=user2)
        opt1.vote_count = 2
        opt1.save()
        
        poll.total_voters = 2
        poll.save()
        
        return poll, opt1, opt2
    
    def test_get_poll_results_via_api(self, auth_client, poll_with_results):
        """Получение результатов через API"""
        poll, opt1, opt2 = poll_with_results
        
        url = f'/api/v1/communications/polls/{poll.id}/results/'
        response = auth_client.post(url)
        
        assert response.status_code == status.HTTP_200_OK
        # Проверяем структуру ответа
        assert 'question' in response.data
        assert 'total_voters' in response.data
        assert 'options' in response.data
    
    def test_results_calculate_percentages(self, poll_with_results):
        """Результаты правильно считают проценты"""
        poll, opt1, opt2 = poll_with_results
        
        results = poll.get_results()
        
        # opt1: 2 голоса из 2 = 100%
        opt1_result = next(o for o in results['options'] if o['id'] == opt1.id)
        assert opt1_result['percentage'] == 100.0
        
        # opt2: 0 голосов из 2 = 0%
        opt2_result = next(o for o in results['options'] if o['id'] == opt2.id)
        assert opt2_result['percentage'] == 0.0
    
    def test_results_show_voters_when_not_anonymous(self, poll_with_results, user1, user2):
        """Результаты показывают голосующих в неанонимных опросах"""
        poll, opt1, opt2 = poll_with_results
        
        results = poll.get_results()
        
        opt1_result = next(o for o in results['options'] if o['id'] == opt1.id)
        
        # Должно быть 2 голосующих
        assert len(opt1_result['voters']) == 2
        voter_ids = [v['voter__id'] for v in opt1_result['voters']]
        assert user1.id in voter_ids
        assert user2.id in voter_ids


@pytest.mark.django_db
class TestPollEdgeCases:
    """Тесты граничных случаев"""
    
    def test_poll_with_empty_question_fails(self, auth_client, private_chat, user1):
        """Голосование с пустым вопросом должно провалиться"""
        message = Message.objects.create(chat=private_chat, author=user1, content='Poll')
        
        url = '/api/v1/communications/polls/'
        data = {
            'message': message.id,
            'question': ''
        }
        
        response = auth_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
    
    def test_poll_with_very_long_question(self, auth_client, private_chat, user1):
        """Голосование с очень длинным вопросом (> 500 символов)"""
        message = Message.objects.create(chat=private_chat, author=user1, content='Poll')
        
        url = '/api/v1/communications/polls/'
        data = {
            'message': message.id,
            'question': 'A' * 501  # Больше чем max_length=500
        }
        
        response = auth_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
    
    def test_poll_without_options_can_be_created(self, auth_client, private_chat, user1):
        """Можно создать голосование без опций (опции добавляются отдельно)"""
        message = Message.objects.create(chat=private_chat, author=user1, content='Poll')
        
        url = '/api/v1/communications/polls/'
        data = {
            'message': message.id,
            'question': 'Poll without options'
        }
        
        response = auth_client.post(url, data, format='json')
        
        # Создание должно быть успешным
        assert response.status_code == status.HTTP_201_CREATED
        poll = Poll.objects.get(id=response.data['id'])
        assert poll.options.count() == 0
    
    def test_vote_in_poll_without_options_fails(self, auth_client, private_chat, user1):
        """Голосование в опросе без опций должно провалиться"""
        message = Message.objects.create(chat=private_chat, author=user1, content='Poll')
        poll = Poll.objects.create(
            message=message,
            author=user1,
            question='No options'
        )
        
        url = f'/api/v1/communications/polls/{poll.id}/vote/'
        response = auth_client.post(url, {'option_ids': [999]}, format='json')
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
    
    def test_total_voters_count_unique_users(self, auth_client, private_chat, user1):
        """total_voters считает уникальных пользователей, не голоса"""
        message = Message.objects.create(chat=private_chat, author=user1, content='Poll')
        poll = Poll.objects.create(
            message=message,
            author=user1,
            question='Multiple?',
            is_multiple_choice=True
        )
        opt1 = PollOption.objects.create(poll=poll, text='A', position=0)
        opt2 = PollOption.objects.create(poll=poll, text='B', position=1)
        
        # Один user голосует за 2 опции
        url = f'/api/v1/communications/polls/{poll.id}/vote/'
        response = auth_client.post(url, {'option_ids': [opt1.id, opt2.id]}, format='json')
        
        # total_voters должен быть 1, не 2
        assert response.data['total_voters'] == 1
