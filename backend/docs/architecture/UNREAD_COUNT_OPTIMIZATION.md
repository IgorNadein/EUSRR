# Оптимизация счетчика непрочитанных сообщений: решение N+1 проблемы

## Проблема

### Текущая реализация

```python
# В ChatViewSet.get_queryset():
unread_count_subq = Message.objects.filter(
    chat=OuterRef('pk'),
    id__gt=Coalesce(Subquery(read_state_subq), 0),
    is_deleted=False
).exclude(author=user).values('chat').annotate(
    count=Count('id')
).values('count')

queryset = Chat.objects.annotate(
    unread_count=unread_count_subq  # ← ПОДЗАПРОС для КАЖДОГО чата!
)
```

### Что происходит:

При загрузке **100 чатов** генерируется SQL вида:

```sql
SELECT 
    chat.id,
    chat.name,
    -- ... другие поля
    (
        SELECT COUNT(*) 
        FROM communications_message m
        WHERE m.chat_id = chat.id 
          AND m.id > COALESCE(
              (SELECT last_read_message_id FROM communications_chatreadstate ...),
              0
          )
          AND m.is_deleted = FALSE
    ) AS unread_count  -- ← Этот подзапрос выполняется для КАЖДОЙ строки!
FROM communications_chat chat
WHERE ...
```

**Проблема:** PostgreSQL выполняет scalar subquery **для каждого чата** в результате.  
Для 100 чатов → ~100 дополнительных вычислений внутри одного запроса.

## Решение: Денормализация

### 1. Добавляем поле в ChatReadState

```python
class ChatReadState(models.Model):
    chat = ForeignKey(Chat)
    user = ForeignKey(Employee)
    last_read_message = ForeignKey(Message, null=True)
    
    # НОВОЕ ПОЛЕ: кешируем количество непрочитанных
    unread_count = models.IntegerField(
        default=0,
        verbose_name="Непрочитанных сообщений"
    )
    updated_at = DateTimeField(auto_now=True)
```

### 2. Обновляем счетчик при событиях

#### При создании нового сообщения:

```python
# В MessageViewSet.create() или signals.py:
@receiver(post_save, sender=Message)
def increment_unread_count(sender, instance, created, **kwargs):
    if not created or instance.is_deleted:
        return
    
    # Получаем всех участников чата (кроме автора)
    participants = instance.chat.get_participants.exclude(id=instance.author_id)
    
    # Инкрементируем счетчик для всех, кто не прочитал
    for participant in participants:
        ChatReadState.objects.filter(
            chat=instance.chat,
            user=participant,
            last_read_message_id__lt=instance.id  # Только если не прочитали
        ).update(
            unread_count=F('unread_count') + 1
        )
        
        # Или создаем новую запись если её нет
        ChatReadState.objects.get_or_create(
            chat=instance.chat,
            user=participant,
            defaults={
                'unread_count': 1,
                'last_read_message': None
            }
        )
```

#### При обновлении last_read_message:

```python
# В ChatViewSet._auto_mark_read():
def _auto_mark_read(self, chat, user, messages):
    if not messages:
        return
    
    last_message = messages[-1]
    
    read_state, created = ChatReadState.objects.get_or_create(
        chat=chat,
        user=user,
        defaults={
            'last_read_message': last_message,
            'unread_count': 0  # читаем → обнуляем
        }
    )
    
    if not created:
        # Защита от откатов
        if read_state.last_read_message_id and \
           last_message.id <= read_state.last_read_message_id:
            return
        
        # Обновляем и обнуляем счетчик
        read_state.last_read_message = last_message
        read_state.unread_count = 0
        read_state.save(update_fields=['last_read_message', 'unread_count', 'updated_at'])
```

### 3. Упрощаем get_queryset()

```python
def get_queryset(self):
    user = self.request.user
    
    # Теперь просто JOIN вместо подзапроса!
    queryset = Chat.objects.filter(
        Q(participants=user) |
        Q(department__in=user.departments_links.filter(
            is_active=True
        ).values('department')) |
        Q(include_all_employees=True)
    ).select_related(
        'department', 'created_by'
    ).prefetch_related(
        'participants',
        Prefetch(
            'read_states',
            queryset=ChatReadState.objects.filter(user=user),
            to_attr='my_read_state'
        )
    ).distinct().order_by('-created_at')
    
    return queryset
```

### 4. В сериализаторе:

```python
class ChatListSerializer(serializers.ModelSerializer):
    unread_count = serializers.SerializerMethodField()
    
    def get_unread_count(self, obj):
        # Используем prefetch'нутый атрибут
        if hasattr(obj, 'my_read_state') and obj.my_read_state:
            return obj.my_read_state[0].unread_count
        return 0
```

## Сравнение производительности

| Метод | SQL запросов | Подзапросы | Сложность |
|-------|--------------|------------|-----------|
| **Текущий** (subquery) | 1 | 100+ scalar subqueries | O(N) в SQL |
| **Денормализация** | 1 | 0 | O(1) |

### SQL с денормализацией:

```sql
-- Один простой JOIN вместо 100 подзапросов!
SELECT 
    chat.*,
    read_state.unread_count  -- ← Просто поле из JOIN
FROM communications_chat chat
LEFT JOIN communications_chatreadstate read_state 
    ON read_state.chat_id = chat.id AND read_state.user_id = 123
WHERE ...
```

## Trade-offs

### Плюсы денормализации:
✅ **O(1)** чтение - просто JOIN по индексу  
✅ Один SQL запрос без подзапросов  
✅ Масштабируется до миллионов чатов  
✅ Можно добавить индекс на `(chat_id, user_id, unread_count)`  

### Минусы:
⚠️ Нужно обновлять при каждом новом сообщении (bulk update)  
⚠️ Риск рассинхронизации (решается периодическим пересчетом)  
⚠️ Немного сложнее логика (но стандартная практика)  

## Миграция

```python
# Создаем миграцию:
python manage.py makemigrations

# В миграции добавляем data migration для пересчета:
def recalculate_unread_counts(apps, schema_editor):
    ChatReadState = apps.get_model('communications', 'ChatReadState')
    Message = apps.get_model('communications', 'Message')
    
    for read_state in ChatReadState.objects.select_related('chat', 'user'):
        # Считаем непрочитанные
        if read_state.last_read_message_id:
            count = Message.objects.filter(
                chat=read_state.chat,
                id__gt=read_state.last_read_message_id,
                is_deleted=False
            ).exclude(author=read_state.user).count()
        else:
            count = Message.objects.filter(
                chat=read_state.chat,
                is_deleted=False
            ).exclude(author=read_state.user).count()
        
        read_state.unread_count = count
        read_state.save(update_fields=['unread_count'])

class Migration(migrations.Migration):
    operations = [
        migrations.AddField(
            model_name='chatreadstate',
            name='unread_count',
            field=models.IntegerField(default=0),
        ),
        migrations.RunPython(recalculate_unread_counts),
    ]
```

## Альтернативы

### Вариант 2: Raw SQL с Window Functions (PostgreSQL)

```python
from django.db import connection

def get_chats_with_unread(user_id):
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT 
                c.*,
                COUNT(m.id) FILTER (
                    WHERE m.id > COALESCE(rs.last_read_message_id, 0)
                      AND m.is_deleted = FALSE
                      AND m.author_id != %s
                ) AS unread_count
            FROM communications_chat c
            LEFT JOIN communications_chatreadstate rs 
                ON rs.chat_id = c.id AND rs.user_id = %s
            LEFT JOIN communications_message m 
                ON m.chat_id = c.id
            WHERE ... -- фильтры участников
            GROUP BY c.id, rs.last_read_message_id
        """, [user_id, user_id])
        
        return cursor.fetchall()
```

**Проблема:** Теряем возможности Django ORM (сериализация, фильтры, пагинация).

### Вариант 3: Кэширование в Redis

```python
# При создании сообщения:
redis_client.hincrby(f'unread:{user_id}', f'chat:{chat_id}', 1)

# При чтении:
redis_client.hset(f'unread:{user_id}', f'chat:{chat_id}', 0)
```

**Проблема:** Еще одна система для синхронизации, risk of data loss.

## Рекомендация

**Используйте денормализацию** - это стандартный паттерн для счетчиков:
- Instagram, Twitter, Facebook - все используют счетчики в БД
- Trade-off: немного дороже запись, но НАМНОГО быстрее чтение
- Чтение происходит в 100x чаще, чем запись сообщений

## Реализация

Готов реализовать:
1. Добавить поле `unread_count` в `ChatReadState`
2. Создать миграцию с пересчетом
3. Обновить `_auto_mark_read()`
4. Добавить signal для инкремента при новом сообщении
5. Упростить `get_queryset()` и сериализатор

Делаем?
