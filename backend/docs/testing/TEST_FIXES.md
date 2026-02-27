# Исправления тестов для работы с реальным API

## Проблемы которые были исправлены:

### 1. ❌ Модель Employee требует phone_number
**Проблема:** `User.objects.create_user()` требует обязательный `phone_number`

**Решение:**
```python
user = User.objects.create_user(
    email='test@example.com',
    password='testpass123',
    phone_number='+79991234567',  # ← Обязательное поле
    first_name='Test',
    last_name='User',
    send_activation_email=False
)
user.email_verified = True  # ← Активируем для тестов
user.is_active = True
user.save()
```

### 2. ❌ Модель Employee не имеет поля `username`
**Проблема:** `Employee.username = None` - email используется как USERNAME_FIELD

**Решение:** Убрали `username='testuser'` из create_user()

### 3. ❌ Chat.members не существует
**Проблема:** Модель Chat использует `participants` вместо `members`

**Решение:**
```python
chat.participants.add(test_user)  # ← Вместо chat.members.add()
```

### 4. ❌ @login_required редиректит на /auth/login/
**Проблема:** View использует `@login_required`, `force_authenticate()` не работает

**Решение:**
```python
api_client.force_login(test_user)  # ← Вместо force_authenticate()
```

### 5. ❌ API возвращает 'messages' вместо 'results'
**Проблема:** Формат ответа отличается от DRF стандарта

**Решение:**
```python
data['messages']  # ← Вместо data['results']
```

### 6. ❌ API возвращает разные поля для разных направлений

**Backwards loading (без after_id):**
```json
{
    "ok": true,
    "messages": [...],
    "has_more": true,
    "has_more_before": true,
    "next_before_id": 50,
    "next_before_ts": 1234567890000
}
```

**Forwards loading (с after_id):**
```json
{
    "ok": true,
    "messages": [...],
    "has_more": false,
    "has_more_after": true,
    "next_after_id": 70,
    "next_after_ts": 1234567890000
}
```

## Следующие шаги:

1. ✅ TestStandardLoading::test_load_latest_messages - ИСПРАВЛЕН
2. ⏳ Исправить остальные тесты под реальный формат API
3. ⏳ Обновить фикстуры для корректного создания тестовых данных
4. ⏳ Добавить проверки has_more_before/has_more_after в зависимости от типа запроса

## Команда для быстрого запуска:

```bash
cd backend
../.venv/Scripts/python -m pytest tests/test_bidirectional_chat_loading.py -v
```
