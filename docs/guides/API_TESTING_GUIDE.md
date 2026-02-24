# Руководство по тестированию API

## Содержание

1. [Инструменты для тестирования](#инструменты-для-тестирования)
2. [Postman](#postman)
3. [REST Client (VS Code)](#rest-client-vs-code)
4. [Pytest (автоматизированные тесты)](#pytest-автоматизированные-тесты)
5. [cURL примеры](#curl-примеры)

## Инструменты для тестирования

### Postman

**Импорт коллекции:**

1. Откройте Postman
2. Нажмите `Import`
3. Выберите файл `EUSRR_API.postman_collection.json` из корня проекта
4. Коллекция будет импортирована со всеми запросами

**Настройка переменных:**

Postman коллекция использует переменные:
- `base_url` - базовый URL API (по умолчанию `http://localhost:8000`)
- `access_token` - JWT токен (автоматически сохраняется после Login)
- `refresh_token` - токен обновления

**Порядок работы:**

1. Запустите запрос **Authentication > Login**
2. Токены автоматически сохранятся в переменные
3. Все остальные запросы будут использовать `access_token` автоматически
4. При истечении токена используйте **Authentication > Refresh Token**

### REST Client (VS Code)

**Установка:**

```bash
# В VS Code установите расширение
REST Client by Huachao Mao
```

**Использование:**

1. Откройте файл `api_tests.http` из корня проекта
2. Выполните запрос **Login** (кликните "Send Request" над запросом)
3. Скопируйте полученный `access` токен
4. Замените `@accessToken = your_access_token_here` на реальный токен
5. Теперь можете выполнять любые запросы

**Преимущества:**

- Работает прямо в VS Code
- Легко редактировать и сохранять запросы
- Поддержка переменных
- История запросов

### Pytest (автоматизированные тесты)

**Запуск тестов API:**

```bash
# В Docker контейнере
docker-compose exec web pytest tests/api/

# Или локально через venv
.venv/Scripts/python -m pytest tests/api/

# Запуск конкретного теста
docker-compose exec web pytest tests/api/v1/test_employees.py

# С выводом покрытия
docker-compose exec web pytest tests/api/ --cov=api --cov-report=html
```

**Пример написания теста:**

```python
# tests/api/v1/test_employees.py

import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

@pytest.mark.django_db
class TestEmployeeAPI:
    def test_list_employees_requires_auth(self):
        """Тест: список сотрудников требует авторизации"""
        client = APIClient()
        url = reverse('api:v1:employees-list')
        response = client.get(url)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_list_employees_with_auth(self, authenticated_client, user):
        """Тест: авторизованный пользователь может получить список"""
        url = reverse('api:v1:employees-list')
        response = authenticated_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert 'results' in response.data

    def test_get_current_user(self, authenticated_client, user):
        """Тест: получение информации о текущем пользователе"""
        url = reverse('api:v1:employees-me')
        response = authenticated_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert response.data['email'] == user.email
```

**Fixtures для тестов:**

```python
# tests/conftest.py

import pytest
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken
from employees.models import Employee

@pytest.fixture
def api_client():
    """Базовый API клиент"""
    return APIClient()

@pytest.fixture
def user(db):
    """Создание тестового пользователя"""
    return Employee.objects.create_user(
        email='test@example.com',
        password='testpass123',
        first_name='Test',
        last_name='User'
    )

@pytest.fixture
def authenticated_client(api_client, user):
    """API клиент с авторизацией"""
    refresh = RefreshToken.for_user(user)
    api_client.credentials(
        HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}'
    )
    return api_client
```

## cURL примеры

### Получение токена

```bash
curl -X POST http://localhost:8000/api/auth/token/ \
  -H "Content-Type: application/json" \
  -d '{
    "username": "admin@example.com",
    "password": "password"
  }'
```

### Список сотрудников

```bash
TOKEN="your_access_token_here"

curl -X GET http://localhost:8000/api/v1/employees/ \
  -H "Authorization: Bearer $TOKEN"
```

### Создание поста

```bash
TOKEN="your_access_token_here"

curl -X POST http://localhost:8000/api/v1/posts/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "content": "Новый пост через cURL!"
  }'
```

### Отправка сообщения

```bash
TOKEN="your_access_token_here"

curl -X POST http://localhost:8000/api/v1/communications/messages/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "chat": 1,
    "content": "Привет из cURL!"
  }'
```

## Типичные сценарии тестирования

### 1. Проверка аутентификации

```bash
# 1. Получить токен
# 2. Проверить доступ к защищенному endpoint
# 3. Проверить, что без токена доступ запрещен
```

### 2. CRUD операции

```bash
# Create - создать ресурс
# Read - получить список и конкретный ресурс
# Update - обновить ресурс (PUT/PATCH)
# Delete - удалить ресурс
```

### 3. Пагинация

```bash
GET /api/v1/employees/?page=1
GET /api/v1/employees/?page=2&page_size=20
```

### 4. Фильтрация

```bash
GET /api/v1/employees/?search=Иванов
GET /api/v1/requests/?status=pending
GET /api/v1/documents/?document_type=report
```

### 5. Сортировка

```bash
GET /api/v1/employees/?ordering=last_name
GET /api/v1/posts/?ordering=-created_at
```

## Проверка WebSocket соединений

### Использование wscat

```bash
# Установка wscat
npm install -g wscat

# Подключение к WebSocket
wscat -c "ws://localhost:8000/ws/chat/1/?token=YOUR_ACCESS_TOKEN"

# Отправка сообщения
{"type": "message", "content": "Hello!"}
```

### Использование Python

```python
import websocket
import json

def on_message(ws, message):
    print(f"Received: {message}")

def on_error(ws, error):
    print(f"Error: {error}")

def on_open(ws):
    print("Connection opened")
    # Отправить сообщение
    ws.send(json.dumps({
        "type": "message",
        "content": "Hello from Python!"
    }))

token = "YOUR_ACCESS_TOKEN"
ws_url = f"ws://localhost:8000/ws/chat/1/?token={token}"

ws = websocket.WebSocketApp(
    ws_url,
    on_message=on_message,
    on_error=on_error,
    on_open=on_open
)

ws.run_forever()
```

## Тестирование производительности

### Apache Bench (ab)

```bash
# Установка (обычно входит в Apache)
# На Windows: скачать с https://www.apachelounge.com/

# Тест производительности
ab -n 1000 -c 10 \
  -H "Authorization: Bearer YOUR_TOKEN" \
  http://localhost:8000/api/v1/employees/
```

### Locust

```python
# locustfile.py

from locust import HttpUser, task, between

class EUSRRUser(HttpUser):
    wait_time = between(1, 3)
    token = None

    def on_start(self):
        """Логин при старте"""
        response = self.client.post("/api/auth/token/", json={
            "username": "admin@example.com",
            "password": "password"
        })
        self.token = response.json()["access"]

    @task(3)
    def list_employees(self):
        self.client.get(
            "/api/v1/employees/",
            headers={"Authorization": f"Bearer {self.token}"}
        )

    @task(2)
    def list_posts(self):
        self.client.get(
            "/api/v1/posts/",
            headers={"Authorization": f"Bearer {self.token}"}
        )

    @task(1)
    def create_post(self):
        self.client.post(
            "/api/v1/posts/",
            json={"content": "Load test post"},
            headers={"Authorization": f"Bearer {self.token}"}
        )
```

Запуск:

```bash
# Установка
pip install locust

# Запуск
locust -f locustfile.py --host=http://localhost:8000

# Откройте http://localhost:8089 для веб-интерфейса
```

## Мониторинг API

### Django Debug Toolbar

Уже установлен в проекте. Доступен в режиме `DEBUG=True`:
- Показывает SQL запросы
- Время выполнения
- Используемые шаблоны
- Кеш операции

### Логирование API запросов

```python
# settings.py

LOGGING = {
    'loggers': {
        'api': {
            'handlers': ['console'],
            'level': 'DEBUG',
        },
    },
}
```

## Troubleshooting

### Ошибка 401 Unauthorized

- Проверьте, что токен актуален
- Токены истекают через определенное время (см. `SIMPLE_JWT` настройки)
- Используйте Refresh Token для получения нового Access Token

### Ошибка 403 Forbidden

- Пользователь авторизован, но не имеет прав
- Проверьте permissions в viewsets
- Проверьте группы и роли пользователя

### Ошибка 404 Not Found

- Проверьте URL endpoint
- Убедитесь, что ресурс с таким ID существует

### Ошибка 500 Internal Server Error

- Проверьте логи сервера: `docker-compose logs web`
- Проверьте валидность отправляемых данных
- Проверьте serializers и validators

## Дополнительные ресурсы

- [Django REST Framework Documentation](https://www.django-rest-framework.org/)
- [Postman Documentation](https://learning.postman.com/)
- [REST Client Documentation](https://marketplace.visualstudio.com/items?itemName=humao.rest-client)
- [Pytest Django Plugin](https://pytest-django.readthedocs.io/)
