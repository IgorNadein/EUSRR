# backend/api/v1/communications/poll_views.py
"""API views для голосований"""

import copy

from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import F
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_GET, require_POST

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from communications.models import (
    Chat,
    Message,
    Poll,
    PollOption,
    PollVote,
)


@csrf_protect
@login_required
@require_POST
def create_poll(request):
    """
    Создать голосование в чате.
    
    POST параметры:
    - chat_id: ID чата
    - question: Вопрос голосования
    - options: Список вариантов ответа (массив строк)
    - is_anonymous: Анонимное голосование (опционально)
    - is_multiple_choice: Множественный выбор (опционально)
    - is_quiz: Викторина (опционально)
    - correct_option_index: Индекс правильного ответа для викторины
    - closes_in_minutes: Автозакрытие через N минут (опционально)
    """
    import json
    
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    
    chat_id = data.get('chat_id')
    question = data.get('question', '').strip()
    options = data.get('options', [])
    
    # Валидация
    if not chat_id:
        return JsonResponse({'error': 'chat_id is required'}, status=400)
    
    if not question:
        return JsonResponse(
            {'error': 'question is required'},
            status=400
        )
    
    if not options or len(options) < 2:
        return JsonResponse(
            {'error': 'At least 2 options are required'},
            status=400
        )
    
    if len(options) > 10:
        return JsonResponse(
            {'error': 'Maximum 10 options allowed'},
            status=400
        )
    
    # Проверка доступа к чату
    chat = get_object_or_404(Chat, id=chat_id)
    
    # TODO: проверить права пользователя на отправку в чат
    # Можно использовать существующую функцию user_can_access_chat
    
    # Настройки голосования
    is_anonymous = data.get('is_anonymous', False)
    is_multiple_choice = data.get('is_multiple_choice', False)
    is_quiz = data.get('is_quiz', False)
    correct_option_index = data.get('correct_option_index')
    closes_in_minutes = data.get('closes_in_minutes')
    
    # Викторина требует правильный ответ
    if is_quiz and correct_option_index is None:
        return JsonResponse(
            {'error': 'Quiz requires correct_option_index'},
            status=400
        )
    
    if is_quiz and not (0 <= correct_option_index < len(options)):
        return JsonResponse(
            {'error': 'Invalid correct_option_index'},
            status=400
        )
    
    # Создание голосования
    with transaction.atomic():
        # Создаём сообщение
        message = Message.objects.create(
            chat=chat,
            author=request.user,
            content=f"📊 {question}",
            is_system=False
        )
        
        # Создаём голосование
        poll = Poll.objects.create(
            message=message,
            author=request.user,
            question=question,
            is_anonymous=is_anonymous,
            is_multiple_choice=is_multiple_choice,
            is_quiz=is_quiz
        )
        
        # Автозакрытие
        if closes_in_minutes:
            poll.closes_at = timezone.now() + timezone.timedelta(
                minutes=closes_in_minutes
            )
            poll.save(update_fields=['closes_at'])
        
        # Создаём варианты ответов
        poll_options = []
        for idx, option_text in enumerate(options):
            if not option_text.strip():
                continue
            
            is_correct = (is_quiz and idx == correct_option_index)
            
            poll_option = PollOption.objects.create(
                poll=poll,
                text=option_text.strip(),
                position=idx,
                is_correct=is_correct
            )
            poll_options.append(poll_option)
    
    # Отправка через WebSocket
    channel_layer = get_channel_layer()
    if channel_layer:
        from communications.consumers import serialize_message
        
        # Перезагружаем сообщение со всеми связанными объектами
        message = Message.objects.select_related(
            'author',
            'reply_to',
            'reply_to__author',
            'forwarded_from_author',
            'poll'
        ).prefetch_related(
            'attachments',
            'reactions',
            'reactions__user',
            'poll__options'
        ).get(pk=message.id)
        
        payload = serialize_message(message)
        group_name = f'chat_{chat_id}'
        
        async_to_sync(channel_layer.group_send)(
            group_name,
            {
                'type': 'chat.message',
                'chat_id': chat.id,
                'payload': payload
            }
        )
    
    return JsonResponse({
        'success': True,
        'poll_id': poll.id,
        'message_id': message.id
    })


@csrf_protect
@login_required
@require_POST
def vote_poll(request, poll_id):
    """
    Проголосовать в голосовании.
    
    URL параметры:
    - poll_id: ID голосования
    
    POST параметры:
    - option_ids: Массив ID выбранных вариантов
    """
    import json
    
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    
    option_ids = data.get('option_ids', [])
    
    if not option_ids:
        return JsonResponse(
            {'error': 'option_ids is required'},
            status=400
        )
    
    # Получаем голосование
    poll = get_object_or_404(
        Poll.objects.select_related('message__chat'),
        id=poll_id
    )
    
    # Проверки
    if poll.is_closed:
        return JsonResponse(
            {'error': 'Poll is closed'},
            status=400
        )
    
    # Автозакрытие
    if poll.closes_at and poll.closes_at <= timezone.now():
        poll.close()
        return JsonResponse(
            {'error': 'Poll has expired'},
            status=400
        )
    
    # Проверка множественного выбора
    if not poll.is_multiple_choice and len(option_ids) > 1:
        return JsonResponse(
            {'error': 'Multiple choice not allowed'},
            status=400
        )
    
    # Проверка доступа к чату
    chat = poll.message.chat
    # TODO: проверить user_can_access_chat
    
    with transaction.atomic():
        # Удаляем старые голоса пользователя (если меняет выбор)
        old_votes = PollVote.objects.filter(
            poll=poll,
            voter=request.user
        )
        
        had_voted = old_votes.exists()
        old_option_ids = set(old_votes.values_list('option_id', flat=True))
        
        # Обновляем счётчики старых вариантов
        for old_vote in old_votes:
            PollOption.objects.filter(
                id=old_vote.option_id
            ).update(vote_count=F('vote_count') - 1)
        
        old_votes.delete()
        
        # Создаём новые голоса
        new_votes = []
        for option_id in option_ids:
            # Проверяем что вариант принадлежит этому голосованию
            option = get_object_or_404(
                PollOption,
                id=option_id,
                poll=poll
            )
            
            vote = PollVote.objects.create(
                poll=poll,
                option=option,
                voter=request.user
            )
            new_votes.append(vote)
            
            # Увеличиваем счётчик
            PollOption.objects.filter(id=option_id).update(
                vote_count=F('vote_count') + 1
            )
        
        # Обновляем счётчик уникальных голосующих
        if not had_voted:
            Poll.objects.filter(id=poll.id).update(
                total_voters=F('total_voters') + 1
            )
    
    # Получаем обновлённые результаты
    poll.refresh_from_db()
    results = poll.get_results()
    user_vote_ids = list(PollVote.objects.filter(
        poll=poll,
        voter=request.user
    ).values_list('option_id', flat=True))
    results_for_user = copy.deepcopy(results)
    results_for_user['user_voted_option_ids'] = user_vote_ids
    
    # Отправка обновления через WebSocket
    channel_layer = get_channel_layer()
    if channel_layer:
        group_name = f'chat_{chat.id}'
        
        ws_message = {
            'type': 'chat.poll_update',  # Правильный формат для group_send
            'chat_id': chat.id,
            'payload': {
                'poll_id': poll.id,
                'message_id': poll.message.id,
                'results': results
            }
        }
        
        async_to_sync(channel_layer.group_send)(
            group_name,
            ws_message
        )
    
    return JsonResponse({
        'success': True,
        'results': results_for_user
    })


@csrf_protect
@login_required
@require_POST
def close_poll(request, poll_id):
    """
    Закрыть голосование (только автор или модератор).
    
    URL параметры:
    - poll_id: ID голосования
    """
    poll = get_object_or_404(
        Poll.objects.select_related('message__chat'),
        id=poll_id
    )
    
    # Проверка прав (только автор)
    if poll.author != request.user:
        # TODO: проверить модераторские права
        return JsonResponse(
            {'error': 'Only author can close poll'},
            status=403
        )
    
    poll.close()
    
    # Отправка обновления через WebSocket
    channel_layer = get_channel_layer()
    if channel_layer:
        group_name = f'chat_{poll.message.chat.id}'
        
        ws_message = {
            'type': 'chat.poll_update',  # Правильный формат для group_send
            'chat_id': poll.message.chat.id,
            'payload': {
                'poll_id': poll.id,
                'message_id': poll.message.id,
                'results': poll.get_results()
            }
        }
        
        async_to_sync(channel_layer.group_send)(
            group_name,
            ws_message
        )
    
    return JsonResponse({'success': True})


@login_required
@require_GET
def get_poll_results(request, poll_id):
    """Получить результаты голосования"""
    
    poll = get_object_or_404(
        Poll.objects.select_related('message__chat'),
        id=poll_id
    )
    
    # Проверка доступа к чату
    # TODO: user_can_access_chat
    
    results = poll.get_results()
    
    # Добавляем информацию о голосе текущего пользователя
    user_votes = PollVote.objects.filter(
        poll=poll,
        voter=request.user
    ).values_list('option_id', flat=True)
    
    results['user_voted_option_ids'] = list(user_votes)
    
    return JsonResponse(results)
