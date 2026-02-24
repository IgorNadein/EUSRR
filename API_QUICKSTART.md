# 🚀 Быстрый старт: Тестирование API

## Выбор инструмента

| Инструмент | Использование | Сложность |
|------------|---------------|-----------|
| **Postman** | GUI, удобный интерфейс | ⭐⭐ |
| **REST Client** | VS Code, быстрое тестирование | ⭐ |
| **pytest** | Автоматизация, CI/CD | ⭐⭐⭐ |
| **cURL** | Консоль, скрипты | ⭐⭐ |

## 1️⃣ Postman (рекомендуется для начинающих)

### Установка
1. Скачайте [Postman](https://www.postman.com/downloads/)
2. Установите и запустите

### Импорт коллекции
```bash
1. File → Import
2. Выберите файл: EUSRR_API.postman_collection.json
3. Также импортируйте: EUSRR_Local.postman_environment.json
4. Выберите environment "EUSRR Local" в правом верхнем углу
```

### Первый запрос
```bash
1. Откройте "Authentication → Login"
2. Нажмите "Send"
3. Токен автоматически сохранится! ✅
4. Теперь можно выполнять любые запросы
```

## 2️⃣ REST Client (для VS Code)

### Установка
```bash
1. Откройте Extensions (Ctrl+Shift+X)
2. Найдите "REST Client"
3. Установите от Huachao Mao
```

### Использование
```bash
1. Откройте файл: api_tests.http
2. Найдите "### Login"
3. Нажмите "Send Request" над запросом
4. Скопируйте access token
5. Замените @accessToken на ваш токен
6. Готово! 🎉
```

## 3️⃣ pytest (автоматизированное тестирование)

### Запуск всех тестов
```bash
# В Docker
docker-compose exec web pytest tests/api/

# Локально
.venv/Scripts/python -m pytest tests/api/
```

### Запуск конкретного теста
```bash
docker-compose exec web pytest tests/api/examples/test_api_examples.py::TestAuthentication::test_login_with_email -v
```

### С покрытием кода
```bash
docker-compose exec web pytest tests/api/ --cov=api --cov-report=html
```

## 4️⃣ cURL (консоль)

### Получить токен
```bash
curl -X POST http://localhost:8000/api/auth/token/ \
  -H "Content-Type: application/json" \
  -d '{"username": "admin@example.com", "password": "password"}'
```

### Использовать токен
```bash
TOKEN="your_token_here"

curl -X GET http://localhost:8000/api/v1/employees/ \
  -H "Authorization: Bearer $TOKEN"
```

## 📋 Основные endpoints

### Аутентификация
- `POST /api/auth/token/` - Получить токен
- `POST /api/auth/token/refresh/` - Обновить токен
- `POST /api/v1/auth/register/` - Регистрация

### Сотрудники
- `GET /api/v1/employees/` - Список
- `GET /api/v1/employees/me/` - Текущий пользователь
- `GET /api/v1/employees/{id}/` - Конкретный сотрудник
- `PATCH /api/v1/employees/{id}/` - Обновить

### Посты
- `GET /api/v1/posts/` - Список
- `POST /api/v1/posts/` - Создать
- `POST /api/v1/posts/{id}/like/` - Лайк

### Мессенджер
- `GET /api/v1/communications/chats/` - Чаты
- `GET /api/v1/communications/messages/?chat={id}` - Сообщения
- `POST /api/v1/communications/messages/` - Отправить

### Документы
- `GET /api/v1/documents/` - Список
- `POST /api/v1/documents/` - Создать
- `GET /api/v1/documents/{id}/` - Получить

### Заявки
- `GET /api/v1/requests/` - Список  
- `POST /api/v1/requests/` - Создать
- `PATCH /api/v1/requests/{id}/` - Обновить

### Уведомления
- `GET /api/v1/notifications/` - Список
- `POST /api/v1/notifications/{id}/mark_as_read/` - Пометить прочитанным

## 🔐 Пример авторизованного запроса

### Postman
```
Authorization: Bearer {{access_token}}
(автоматически подставляется)
```

### REST Client
```http
GET {{baseUrl}}/api/v1/employees/
Authorization: Bearer {{accessToken}}
```

### cURL
```bash
curl -H "Authorization: Bearer YOUR_TOKEN" \
  http://localhost:8000/api/v1/employees/
```

### Python requests
```python
import requests

token = "your_token"
headers = {"Authorization": f"Bearer {token}"}
response = requests.get(
    "http://localhost:8000/api/v1/employees/",
    headers=headers
)
```

## ⚠️ Частые ошибки

### 401 Unauthorized
```
❌ Токен отсутствует или истек
✅ Выполните Login снова
```

### 403 Forbidden
```
❌ Нет прав доступа
✅ Проверьте роль пользователя
```

### 404 Not Found
```
❌ Неверный URL или ID
✅ Проверьте endpoint
```

### 400 Bad Request
```
❌ Ошибка в данных запроса
✅ Проверьте JSON и обязательные поля
```

## 📚 Полная документация

Детальная документация: [docs/guides/API_TESTING_GUIDE.md](docs/guides/API_TESTING_GUIDE.md)

## 🎯 Следующие шаги

1. ✅ Выберите инструмент тестирования
2. ✅ Импортируйте коллекцию/откройте файл
3. ✅ Выполните Login
4. ✅ Протестируйте endpoints
5. ✅ Изучите примеры тестов

**Вопросы?** Смотрите [API_TESTING_GUIDE.md](docs/guides/API_TESTING_GUIDE.md)
