# backend/api/v1/schedule/serializers.py
"""
Serializers для django-scheduler.
Чистые, проверенные временем модели.
"""
from rest_framework import serializers
from schedule.models import Calendar, Event, Rule, Occurrence, EventRelation
import pytz


class CalendarSerializer(serializers.ModelSerializer):
    """Сериализатор для Calendar (django-scheduler) с совместимостью EUSRR."""
    
    # Совместимость с EUSRR API - принимаем title, конвертируем в name
    title = serializers.CharField(source='name', required=False)
    events_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Calendar
        fields = ['id', 'name', 'title', 'slug', 'events_count']
        read_only_fields = ['id']
        extra_kwargs = {
            'slug': {'required': False},  # Сделаем auto-generated если не указан
        }
    
    def get_events_count(self, obj):
        """Количество событий в календаре."""
        return obj.event_set.count()
    
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
    
    class Meta:
        model = Rule
        fields = ['id', 'name', 'description', 'frequency', 'params']
        read_only_fields = ['id']


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
            'start',
            'end',
            'calendar',
            'calendar_name',
            'color_event',
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
    
    class Meta:
        model = EventRelation
        fields = [
            'id',
            'event',
            'event_title',
            'content_type',
            'object_id',
            'content_object',
            'user_name',
            'distinction',
            'created_on',
        ]
        read_only_fields = ['id', 'created_on']
    
    def get_user_name(self, obj):
        """Имя связанного объекта."""
        if obj.content_object:
            return str(obj.content_object)
        return None
