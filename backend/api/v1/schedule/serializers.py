# backend/api/v1/schedule/serializers.py
"""
Serializers для django-scheduler.
Чистые, проверенные временем модели.
"""
from rest_framework import serializers
from schedule.models import Calendar, Event, Rule, Occurrence, EventRelation, CalendarRelation
from django.contrib.contenttypes.models import ContentType
import pytz


class CalendarRelationSerializer(serializers.ModelSerializer):
    """Сериализатор для CalendarRelation (участники календаря)."""
    
    user_id = serializers.IntegerField(write_only=True, required=False)
    user = serializers.SerializerMethodField(read_only=True)
    
    class Meta:
        model = CalendarRelation
        fields = ['id', 'calendar', 'user_id', 'user', 'distinction', 'inheritable']
        read_only_fields = ['id']
    
    def get_user(self, obj):
        """Информация о связанном пользователе."""
        if obj.content_object:
            return {
                'id': obj.content_object.id,
                'username': getattr(obj.content_object, 'username', str(obj.content_object)),
                'first_name': getattr(obj.content_object, 'first_name', ''),
                'last_name': getattr(obj.content_object, 'last_name', ''),
            }
        return None
    
    def create(self, validated_data):
        """Создать связь календаря с пользователем."""
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        user_id = validated_data.pop('user_id')
        calendar = validated_data['calendar']
        distinction = validated_data.get('distinction', 'viewer')
        inheritable = validated_data.get('inheritable', True)
        
        user = User.objects.get(id=user_id)
        
        # Используем встроенный метод create_relation
        calendar.create_relation(user, distinction=distinction, inheritable=inheritable)
        
        # Возвращаем созданную relation
        ct = ContentType.objects.get_for_model(User)
        return CalendarRelation.objects.get(
            calendar=calendar,
            content_type=ct,
            object_id=user_id,
            distinction=distinction
        )


class CalendarSerializer(serializers.ModelSerializer):
    """Сериализатор для Calendar (django-scheduler) с совместимостью EUSRR."""
    
    # Совместимость с EUSRR API - принимаем title, конвертируем в name
    title = serializers.CharField(source='name', required=False)
    events_count = serializers.SerializerMethodField()
    owner = serializers.SerializerMethodField()
    participants = serializers.SerializerMethodField()
    user_role = serializers.SerializerMethodField()
    
    class Meta:
        model = Calendar
        fields = ['id', 'name', 'title', 'slug', 'events_count', 'owner', 'participants', 'user_role']
        read_only_fields = ['id', 'owner', 'participants', 'user_role']
        extra_kwargs = {
            'slug': {'required': False},  # Сделаем auto-generated если не указан
        }
    
    def get_events_count(self, obj):
        """Количество событий в календаре."""
        return obj.event_set.count()
    
    def get_owner(self, obj):
        """Получить владельца календаря."""
        try:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            ct = ContentType.objects.get_for_model(User)
            
            owner_relation = CalendarRelation.objects.filter(
                calendar=obj,
                content_type=ct,
                distinction='owner'
            ).first()
            
            if owner_relation and owner_relation.content_object:
                return {
                    'id': owner_relation.content_object.id,
                    'username': getattr(owner_relation.content_object, 'username', str(owner_relation.content_object)),
                    'full_name': str(owner_relation.content_object),
                }
        except Exception:
            pass
        return None
    
    def get_participants(self, obj):
        """Список всех участников календаря."""
        from django.contrib.auth import get_user_model
        User = get_user_model()
        ct = ContentType.objects.get_for_model(User)
        
        relations = CalendarRelation.objects.filter(
            calendar=obj,
            content_type=ct
        ).select_related('content_type')
        
        participants = []
        for rel in relations:
            if rel.content_object:
                participants.append({
                    'id': rel.content_object.id,
                    'username': getattr(rel.content_object, 'username', str(rel.content_object)),
                    'full_name': str(rel.content_object),
                    'role': rel.distinction,
                })
        return participants
    
    def get_user_role(self, obj):
        """Роль текущего пользователя для этого календаря."""
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return None
        
        from django.contrib.auth import get_user_model
        User = get_user_model()
        ct = ContentType.objects.get_for_model(User)
        
        relation = CalendarRelation.objects.filter(
            calendar=obj,
            content_type=ct,
            object_id=request.user.id
        ).first()
        
        return relation.distinction if relation else None
    
    def create(self, validated_data):
        """Создать календарь с автогенерацией slug из name/title."""
        from django.utils.text import slugify
        
        # Если slug не указан - генерируем из name
        if 'slug' not in validated_data or not validated_data.get('slug'):
            name = validated_data.get('name', 'calendar')
            base_slug = slugify(name)
            if not base_slug:
                base_slug = 'calendar'
            
            # Проверяем уникальность slug
            slug = base_slug
            counter = 1
            while Calendar.objects.filter(slug=slug).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            
            validated_data['slug'] = slug
        
        return super().create(validated_data)


class RuleSerializer(serializers.ModelSerializer):
    """Сериализатор для Rule (rrule RFC 5545)."""
    
    # Удобные поля для frontend
    frequency_display = serializers.CharField(source='get_frequency_display', read_only=True)
    
    class Meta:
        model = Rule
        fields = ['id', 'name', 'description', 'frequency', 'frequency_display', 'params']
        read_only_fields = ['id', 'frequency_display']
    
    def to_representation(self, instance):
        """Десериализация params из JSON-строки в dict."""
        import json
        data = super().to_representation(instance)
        
        # Парсим params из строки в объект для frontend
        if data.get('params'):
            try:
                if isinstance(data['params'], str):
                    data['params'] = json.loads(data['params'])
            except (json.JSONDecodeError, TypeError):
                data['params'] = {}
        else:
            data['params'] = {}
        
        return data
    
    def validate_frequency(self, value):
        """Валидация frequency."""
        valid_frequencies = ['YEARLY', 'MONTHLY', 'WEEKLY', 'DAILY', 'HOURLY', 'MINUTELY', 'SECONDLY']
        if value not in valid_frequencies:
            raise serializers.ValidationError(
                f'Invalid frequency. Must be one of: {", ".join(valid_frequencies)}'
            )
        return value


class EventSerializer(serializers.ModelSerializer):
    """Сериализатор для Event (django-scheduler)."""
    
    calendar_name = serializers.CharField(source='calendar.name', read_only=True)
    rule_description = serializers.CharField(source='rule.description', read_only=True, allow_null=True)
    
    class Meta:
        model = Event
        fields = [
            'id',
            'title',
            'description',
            'start',
            'end',
            'calendar',
            'calendar_name',
            'rule',
            'rule_description',
            'end_recurring_period',
            'color_event',
            'creator',
            'created_on',
            'updated_on',
        ]
        read_only_fields = ['id', 'created_on', 'updated_on']
    
    def validate(self, attrs):
        """Валидация start/end."""
        start = attrs.get('start')
        end = attrs.get('end')
        
        if end and start and end < start:
            raise serializers.ValidationError({
                'end': 'Дата окончания не может быть раньше даты начала.'
            })
        
        return attrs


class EventListSerializer(EventSerializer):
    """Упрощённый сериализатор для списка событий."""
    
    class Meta(EventSerializer.Meta):
        fields = [
            'id',
            'title',
            'description',
            'start',
            'end',
            'calendar',
            'calendar_name',
            'color_event',
            'rule',
            'end_recurring_period',
        ]


class OccurrenceSerializer(serializers.ModelSerializer):
    """Сериализатор для Occurrence (материализованные вхождения)."""
    
    event_title = serializers.CharField(source='event.title', read_only=True)
    event_id = serializers.IntegerField(source='event.id', read_only=True)
    
    class Meta:
        model = Occurrence
        fields = [
            'id',
            'event',
            'event_id',
            'event_title',
            'title',
            'description',
            'start',
            'end',
            'cancelled',
            'original_start',
            'original_end',
            'created_on',
            'updated_on',
        ]
        read_only_fields = ['id', 'created_on', 'updated_on']


class EventRelationSerializer(serializers.ModelSerializer):
    """Сериализатор для EventRelation (участники встреч)."""
    
    event_title = serializers.CharField(source='event.title', read_only=True)
    user_name = serializers.SerializerMethodField()
    content_type = serializers.PrimaryKeyRelatedField(
        queryset=ContentType.objects.all(),
        required=False  # Делаем необязательным
    )
    
    class Meta:
        model = EventRelation
        fields = [
            'id',
            'event',
            'event_title',
            'content_type',
            'object_id',
            'distinction',
            'user_name',
        ]
        read_only_fields = ['id']
    
    def get_user_name(self, obj):
        """Имя связанного объекта."""
        if obj.content_object:
            return str(obj.content_object)
        return None
    
    def create(self, validated_data):
        """Автоматически устанавливает content_type для User."""
        if 'content_type' not in validated_data:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            validated_data['content_type'] = ContentType.objects.get_for_model(User)
        return super().create(validated_data)
