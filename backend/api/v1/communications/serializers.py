"""
Serializers for Communications API
"""
from rest_framework import serializers
from django.contrib.auth import get_user_model
from communications.models import (
    Chat, Message, MessageAttachment, 
    MessageReaction, Poll, PollOption, PollVote,
    ChatMembership, ChatUserSettings
)
from communications.serialization import serialize_message

Employee = get_user_model()


class ChatUserSettingsSerializer(serializers.ModelSerializer):
    """Настройки пользователя для чата"""
    
    class Meta:
        model = ChatUserSettings
        fields = ['is_pinned', 'notifications_enabled']


class ChatMembershipSerializer(serializers.ModelSerializer):
    """Членство в чате"""
    user_name = serializers.CharField(source='user.get_full_name', read_only=True)
    
    class Meta:
        model = ChatMembership
        fields = [
            'id', 'user', 'user_name', 'role', 
            'can_send_messages', 'can_manage_members',
            'joined_at'
        ]
        read_only_fields = ['joined_at']


class ChatListSerializer(serializers.ModelSerializer):
    """Сериализатор для списка чатов (облегченный)"""
    last_message = serializers.SerializerMethodField()
    unread_count = serializers.IntegerField(read_only=True)
    participant_names = serializers.SerializerMethodField()
    is_pinned = serializers.SerializerMethodField()
    notifications_enabled = serializers.SerializerMethodField()
    
    class Meta:
        model = Chat
        fields = [
            'id', 'type', 'name', 'description', 'avatar',
            'created_at', 'is_main', 'department',
            'last_message', 'unread_count', 'participant_names',
            'is_pinned', 'notifications_enabled'
        ]
    
    def get_last_message(self, obj):
        """Последнее сообщение в чате"""
        last_msg = obj.messages.filter(is_deleted=False).order_by('-created_at').first()
        if last_msg:
            return {
                'id': last_msg.id,
                'content': last_msg.content[:100],
                'author_name': last_msg.author.get_full_name() if last_msg.author else 'Unknown',
                'created_at': last_msg.created_at.isoformat(),
            }
        return None
    
    def get_participant_names(self, obj):
        """Имена участников (для приватных чатов)"""
        if obj.type == 'private':
            return [p.get_full_name() for p in obj.participants.all()[:5]]
        return []
    
    def get_is_pinned(self, obj):
        """Закреплен ли чат для текущего пользователя"""
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            settings = obj.user_settings.filter(user=request.user).first()
            return settings.is_pinned if settings else False
        return False
    
    def get_notifications_enabled(self, obj):
        """Включены ли уведомления"""
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            settings = obj.user_settings.filter(user=request.user).first()
            return settings.notifications_enabled if settings else True
        return True


class ChatDetailSerializer(serializers.ModelSerializer):
    """Детальный сериализатор чата"""
    participants = serializers.PrimaryKeyRelatedField(
        many=True, 
        queryset=Employee.objects.all(),
        required=False
    )
    participant_details = serializers.SerializerMethodField()
    memberships = ChatMembershipSerializer(many=True, read_only=True, source='chatmembership_set')
    user_settings = serializers.SerializerMethodField()
    
    class Meta:
        model = Chat
        fields = [
            'id', 'type', 'name', 'description', 'avatar',
            'created_by', 'created_at', 'is_main', 
            'include_all_employees', 'department',
            'participants', 'participant_details',
            'memberships', 'user_settings'
        ]
        read_only_fields = ['created_at', 'created_by']
    
    def get_participant_details(self, obj):
        """Детали участников"""
        participants = obj.participants.all()[:20]
        return [{
            'id': p.id,
            'name': p.get_full_name(),
            'avatar': p.avatar.url if p.avatar else None
        } for p in participants]
    
    def get_user_settings(self, obj):
        """Настройки текущего пользователя для чата"""
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            settings = obj.user_settings.filter(user=request.user).first()
            if settings:
                return ChatUserSettingsSerializer(settings).data
        return {'is_pinned': False, 'notifications_enabled': True}


class MessageAttachmentSerializer(serializers.ModelSerializer):
    """Вложение сообщения"""
    
    class Meta:
        model = MessageAttachment
        fields = [
            'id', 'file_name', 'file_type', 'file_size',
            'mime_type', 'file', 'thumbnail', 'uploaded_at',
            'width', 'height'
        ]
        read_only_fields = ['uploaded_at', 'width', 'height']


class MessageReactionSerializer(serializers.ModelSerializer):
    """Реакция на сообщение"""
    user_name = serializers.CharField(source='user.get_full_name', read_only=True)
    
    class Meta:
        model = MessageReaction
        fields = ['id', 'emoji', 'user', 'user_name', 'created_at']
        read_only_fields = ['created_at']


class PollOptionSerializer(serializers.ModelSerializer):
    """Опция голосования"""
    percentage = serializers.SerializerMethodField()
    voters = serializers.SerializerMethodField()
    
    class Meta:
        model = PollOption
        fields = ['id', 'text', 'position', 'vote_count', 'percentage', 'voters']
    
    def get_percentage(self, obj):
        """Процент голосов"""
        if obj.poll and obj.poll.total_voters > 0:
            return round((obj.vote_count / obj.poll.total_voters) * 100, 1)
        return 0
    
    def get_voters(self, obj):
        """Список проголосовавших (если не анонимное)"""
        if obj.poll and obj.poll.is_anonymous:
            return []
        
        # Возвращаем список с именами
        votes = obj.votes.select_related('voter').all()
        return [
            {
                'voter__first_name': vote.voter.first_name,
                'voter__last_name': vote.voter.last_name,
                'voter__id': vote.voter.id
            }
            for vote in votes
        ]


class PollSerializer(serializers.ModelSerializer):
    """Голосование"""
    options = PollOptionSerializer(many=True, read_only=True)
    user_voted_option_ids = serializers.SerializerMethodField()
    
    # Поля для создания (write_only)
    options_data = serializers.ListField(
        child=serializers.CharField(max_length=200),
        write_only=True,
        required=False,
        help_text="Список вариантов ответов (строки)"
    )
    chat_id = serializers.IntegerField(write_only=True, required=True)
    correct_option_index = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    closes_in_minutes = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    
    class Meta:
        model = Poll
        fields = [
            'id', 'message', 'question', 'is_anonymous', 'is_multiple_choice',
            'is_quiz', 'is_closed', 'closes_at', 'allows_custom_answers',
            'total_voters', 'options', 'user_voted_option_ids',
            # write_only поля
            'options_data', 'chat_id', 'correct_option_index', 'closes_in_minutes'
        ]
        read_only_fields = ['id', 'message', 'is_closed', 'total_voters']
    
    def get_user_voted_option_ids(self, obj):
        """ID опций за которые проголосовал текущий пользователь"""
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            votes = obj.votes.filter(voter=request.user)
            return [v.option_id for v in votes]
        return []
    
    def create(self, validated_data):
        """Создание голосования с опциями"""
        from communications.models import Chat, Message, PollOption
        from datetime import timedelta
        from django.utils import timezone
        import logging
        
        logger = logging.getLogger(__name__)
        logger.info(f"[PollSerializer.create] validated_data: {validated_data}")
        
        # Извлекаем данные для создания
        options_data = validated_data.pop('options_data', [])
        chat_id = validated_data.pop('chat_id')
        correct_option_index = validated_data.pop('correct_option_index', None)
        closes_in_minutes = validated_data.pop('closes_in_minutes', None)
        
        logger.info(f"[PollSerializer.create] options_data: {options_data}, chat_id: {chat_id}")
        
        # Получаем автора (может быть передан через perform_create или взять из запроса)
        request = self.context.get('request')
        request_user = getattr(request, 'user', None)
        author = validated_data.pop('author', None) or request_user
        if author is None:
            raise serializers.ValidationError({'author': 'Author is required'})
        
        # Создаем сообщение в чате
        try:
            chat = Chat.objects.get(id=chat_id)
        except Chat.DoesNotExist:
            logger.error(f"[PollSerializer.create] Chat {chat_id} not found")
            raise serializers.ValidationError({'chat_id': 'Chat not found'})
        
        message = Message.objects.create(
            chat=chat,
            author=author,
            content=f"📊 {validated_data['question']}",
            is_system=False
        )
        
        # Устанавливаем closes_at если указано
        if closes_in_minutes and closes_in_minutes > 0:
            validated_data['closes_at'] = timezone.now() + timedelta(minutes=closes_in_minutes)
        
        # Создаем голосование
        poll = Poll.objects.create(
            message=message,
            author=author,
            **validated_data
        )
        
        # Создаем опции
        for index, option_text in enumerate(options_data):
            is_correct = (correct_option_index is not None and index == correct_option_index)
            PollOption.objects.create(
                poll=poll,
                text=option_text,
                position=index,
                is_correct=is_correct
            )
        
        # Отправляем WebSocket уведомление о новом сообщении
        from channels.layers import get_channel_layer
        from asgiref.sync import async_to_sync
        from communications.serialization import serialize_message
        
        # Перезагружаем сообщение с poll и options для полной сериализации
        message.refresh_from_db()
        message_data = serialize_message(message)
        
        channel_layer = get_channel_layer()
        chat_id_value = getattr(chat, 'id', chat_id)
        if channel_layer is not None:
            async_to_sync(channel_layer.group_send)(
                f'chat_{chat_id_value}',
                {
                    'type': 'chat_message',
                    'chat_id': chat_id_value,
                    'payload': message_data
                }
            )
        
        message_id_value = getattr(message, 'id', None)
        logger.info(f"[PollSerializer.create] WebSocket notification sent for message {message_id_value}")
        
        return poll


class MessageListSerializer(serializers.ModelSerializer):
    """Облегченный сериализатор для списка сообщений"""
    author_name = serializers.CharField(source='author.get_full_name', read_only=True)
    author_avatar = serializers.SerializerMethodField()
    reactions_summary = serializers.SerializerMethodField()
    
    class Meta:
        model = Message
        fields = [
            'id', 'content', 'author', 'author_name', 'author_avatar',
            'created_at', 'is_edited', 'edited_at', 'is_deleted',
            'is_pinned', 'has_attachments', 'reactions_summary'
        ]
    
    def get_author_avatar(self, obj):
        if obj.author and obj.author.avatar:
            return obj.author.avatar.url
        return None
    
    def get_reactions_summary(self, obj):
        """Суммарная информация о реакциях"""
        reactions = {}
        for reaction in obj.reactions.all():
            emoji = reaction.emoji
            if emoji not in reactions:
                reactions[emoji] = {'count': 0, 'users': [], 'user_names': []}
            reactions[emoji]['count'] += 1
            reactions[emoji]['users'].append(reaction.user_id)
            reactions[emoji]['user_names'].append(reaction.user.get_full_name())
        return reactions


class MessageDetailSerializer(serializers.ModelSerializer):
    """Детальный сериализатор сообщения (использует функцию serialize_message)"""
    
    class Meta:
        model = Message
        fields = '__all__'
    
    def to_representation(self, instance):
        """Используем существующую функцию сериализации"""
        return serialize_message(instance)


class MessageCreateSerializer(serializers.ModelSerializer):
    """Сериализатор для создания/редактирования сообщений"""
    
    class Meta:
        model = Message
        fields = [
            'content', 'chat', 'reply_to', 'is_forwarded'
        ]
    
    def validate(self, attrs):
        """Валидация: сообщение должно иметь либо текст, либо вложения"""
        content = attrs.get('content', '').strip()
        # Проверка контента будет на уровне view при наличии файлов
        return attrs
    
    def create(self, validated_data):
        """Создание сообщения с автором"""
        validated_data['author'] = self.context['request'].user
        return super().create(validated_data)


class MessageEditSerializer(serializers.Serializer):
    """Сериализатор для редактирования сообщения"""
    content = serializers.CharField(required=False, allow_blank=True)
    existing_attachment_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        allow_empty=True
    )


class ReactionSerializer(serializers.Serializer):
    """Сериализатор для добавления/удаления реакции"""
    emoji = serializers.CharField(max_length=10)


class ForwardMessageSerializer(serializers.Serializer):
    """Сериализатор для пересылки сообщений"""
    message_ids = serializers.ListField(
        child=serializers.IntegerField(),
        min_length=1
    )
    target_chat_id = serializers.IntegerField()


class BulkDeleteSerializer(serializers.Serializer):
    """Сериализатор для массового удаления"""
    message_ids = serializers.ListField(
        child=serializers.IntegerField(),
        min_length=1
    )
