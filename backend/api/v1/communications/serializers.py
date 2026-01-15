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
from communications.consumers import serialize_message

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
    
    class Meta:
        model = PollOption
        fields = ['id', 'text', 'position', 'vote_count', 'percentage']
    
    def get_percentage(self, obj):
        """Процент голосов"""
        if obj.poll and obj.poll.total_voters > 0:
            return round((obj.vote_count / obj.poll.total_voters) * 100, 1)
        return 0


class PollSerializer(serializers.ModelSerializer):
    """Голосование"""
    options = PollOptionSerializer(many=True, read_only=True)
    user_voted_option_ids = serializers.SerializerMethodField()
    
    class Meta:
        model = Poll
        fields = [
            'id', 'question', 'is_anonymous', 'is_multiple_choice',
            'is_quiz', 'is_closed', 'closes_at',
            'total_voters', 'options', 'user_voted_option_ids'
        ]
    
    def get_user_voted_option_ids(self, obj):
        """ID опций за которые проголосовал текущий пользователь"""
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            votes = obj.votes.filter(voter=request.user)
            return [v.option_id for v in votes]
        return []


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
