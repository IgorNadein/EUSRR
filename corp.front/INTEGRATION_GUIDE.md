# Frontend Integration Guide

## Обзор

Фронтенд corp.front полностью интегрирован с Django Backend через REST API. Используется Next.js 16 с TypeScript и Tailwind CSS.

## Структура проекта

```
corp.front/
├── src/
│   ├── app/               # Next.js страницы
│   │   ├── page.tsx       # Главная (Лента) ✅ Интегрирован
│   │   ├── employees/     # Сотрудники ✅ Интегрирован
│   │   ├── departments/   # Отделы
│   │   ├── documents/     # Документы
│   │   ├── messages/      # Сообщения
│   │   ├── requests/      # Заявки
│   │   ├── finances/      # Финансы
│   │   └── login/         # Вход
│   ├── lib/
│   │   └── api.ts         # API клиент ✅
│   ├── types/
│   │   └── api.ts         # TypeScript типы ✅
│   └── hooks/
│       └── useApi.ts      # React хуки для API ✅
```

## API клиент

### Базовая конфигурация

API клиент автоматически:
- Добавляет JWT токен к запросам
- Обрабатывает ошибки авторизации
- Сохраняет токены в localStorage
- Перенаправляет на /login при 401

### Использование

```typescript
import apiClient from '@/lib/api';

// Авторизация
const { access, refresh, user } = await apiClient.login({
  username: 'user@example.com',
  password: 'password'
});

// Получение данных
const employees = await apiClient.getEmployees();
const posts = await apiClient.getPosts();
```

## React хуки

Используйте готовые хуки из `@/hooks/useApi`:

```tsx
import { useCurrentUser, useEmployees, usePosts } from '@/hooks/useApi';

function MyComponent() {
  const { user, loading, error } = useCurrentUser();
  const { employees } = useEmployees({ search: 'John' });
  const { posts } = usePosts({ page: 1 });

  if (loading) return <div>Загрузка...</div>;
  if (error) return <div>Ошибка: {error.message}</div>;

  return <div>{/* UI */}</div>;
}
```

### Доступные хуки

- `useCurrentUser()` - текущий пользователь
- `useEmployees(params?)` - список сотрудников
- `useDepartments()` - список отделов
- `usePosts(params?)` - посты ленты
- `useDocuments(params?)` - документы
- `useRequests(params?)` - заявки
- `useChats()` - чаты
- `useNotifications()` - уведомления

## TypeScript типы

Все типы данных определены в `@/types/api.ts`:

```typescript
import type { User, Post, Department, Document } from '@/types/api';
```

## Интегрированные страницы

### ✅ Главная страница (Лента)

**Файл**: `src/app/page.tsx`

**Функции**:
- Загрузка постов из API
- Отображение автора, времени, контента
- Лайки и комментарии
- Теги постов

**Используемые хуки**:
- `usePosts()` - получение постов
- `useCurrentUser()` - текущий пользователь

### ✅ Сотрудники

**Файл**: `src/app/employees/page.tsx`

**Функции**:
- Список всех сотрудников
- Поиск по имени
- Статус (онлайн/оффлайн)
- Должность и отдел

**Используемые хуки**:
- `useEmployees({ search })` - поиск сотрудников
- `useCurrentUser()` - текущий пользователь

## Переменные окружения

### Для локальной разработки

`.env.local`:
```env
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_WS_URL=ws://localhost:8000
```

### Для Docker

`.env.local` (автоматически используется в docker-compose):
```env
NEXT_PUBLIC_API_URL=http://web:8000
NEXT_PUBLIC_WS_URL=ws://web:8000
```

## Запуск

### Локальная разработка

```bash
cd corp.front
npm install
npm run dev
```

Доступно на: http://localhost:3000

### Docker

```bash
# Из корня проекта
docker-compose up -d frontend
```

Доступно через nginx:  http://localhost

## Интеграция новых страниц

### Шаг 1: Создать страницу

```tsx
// src/app/mypage/page.tsx
"use client";

import { useMyData } from '@/hooks/useApi';

export default function MyPage() {
  const { data, loading, error } = useMyData();

  if (loading) return <div>Загрузка...</div>;
  if (error) return <div>Ошибка: {error.message}</div>;

  return (
    <div>
      {data.map(item => (
        <div key={item.id}>{item.name}</div>
      ))}
    </div>
  );
}
```

### Шаг 2: Добавить метод в API клиент

```typescript
// src/lib/api.ts
class ApiClient {
  // ... existing methods

  async getMyData() {
    return this.request('/mydata/');
  }
}
```

### Шаг 3: Создать хук (опционально)

```typescript
// src/hooks/useApi.ts
export function useMyData() {
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    async function fetchData() {
      try {
        const result = await apiClient.getMyData();
        setData(result);
      } catch (err) {
        setError(err);
      } finally {
        setLoading(false);
      }
    }
    fetchData();
  }, []);

  return { data, loading, error };
}
```

## API Endpoints

Полный список доступных эндпоинтов:

### Auth
- `POST /api/auth/token/` - Login
- `POST /api/auth/token/refresh/` - Refresh token
- `POST /api/v1/auth/register/` - Регистрация

### Employees
- `GET /api/v1/employees/` - Список сотрудников
- `GET /api/v1/employees/{id}/` - Детали сотрудника
- `GET /api/v1/employees/me/` - Текущий пользователь

### Departments
- `GET /api/v1/departments/` - Список отделов
- `GET /api/v1/departments/{id}/` - Детали отдела

### Feed
- `GET /api/v1/posts/` - Посты ленты
- `POST /api/v1/posts/` - Создать пост
- `POST /api/v1/posts/{id}/like/` - Лайк поста
- `GET /api/v1/comments/` - Комментарии
- `POST /api/v1/comments/` - Создать комментарий

### Documents
- `GET /api/v1/documents/` - Документы
- `GET /api/v1/documents/{id}/` - Детали документа

### Requests
- `GET /api/v1/requests/` - Заявки
- `POST /api/v1/requests/` - Создать заявку
- `GET /api/v1/requests/{id}/` - Детали заявки

### Communications
- `GET /api/v1/communications/chats/` - Чаты
- `GET /api/v1/communications/messages/` - Сообщения
- `POST /api/v1/communications/messages/` - Отправить сообщение

### Calendar
- `GET /api/v1/calendar/events/` - События календаря
- `GET /api/v1/calendar/calendars/` - Календари

### Notifications
- `GET /api/v1/notifications/` - Уведомления
- `POST /api/v1/notifications/{id}/mark_read/` - Отметить прочитанным
- `POST /api/v1/notifications/mark_all_read/` - Отметить все прочитанными

## Аутентификация

### Вход

```typescript
import apiClient from '@/lib/api';

async function handleLogin(username: string, password: string) {
  try {
    const { access, refresh, user } = await apiClient.login({
      username,
      password
    });

    // Токен автоматически сохранён
    // Перенаправить пользователя
    router.push('/');
  } catch (error) {
    console.error('Login failed:', error);
  }
}
```

### Выход

```typescript
import apiClient from '@/lib/api';

function handleLogout() {
  apiClient.clearToken();
  router.push('/login');
}
```

### Защищённые страницы

```tsx
"use client";

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import apiClient from '@/lib/api';

export default function ProtectedPage() {
  const router = useRouter();

  useEffect(() => {
    const token = apiClient.getToken();
    if (!token) {
      router.push('/login');
    }
  }, []);

  return <div>Protected content</div>;
}
```

## Обработка ошибок

API клиент автоматически обрабатывает:

- **401 Unauthorized**: Очищает токены и перенаправляет на `/login`
- **Network errors**: Выбрасывает исключение с сообщением

Пример обработки в компонентах:

```tsx
const { data, loading, error } = useMyData();

if (loading) return <LoadingSpinner />;

if (error) {
  return (
    <div className="error-message">
      <h3>Ошибка загрузки данных</h3>
      <p>{error.message}</p>
      <button onClick={() => refetch()}>Попробовать снова</button>
    </div>
  );
}
```

## WebSocket (для будущей реализации)

Для real-time обновлений можно добавить WebSocket соединение:

```typescript
const WS_URL = process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8000';

const socket = new WebSocket(`${WS_URL}/ws/notifications/`);

socket.onmessage = (event) => {
  const data = JSON.parse(event.data);
  // Обработать уведомление
};
```

## Рекомендации

1. **Всегда используйте хуки** для получения данных из API
2. **Обрабатывайте loading и error** состояния в UI
3. **Используйte TypeScript типы** для type-safety
4. **Не сохраняйте чувствительные данные** в localStorage кроме токенов
5. **Валидируйте данные** перед отправкой на сервер

## Troubleshooting

###CORS ошибки

Убедитесь, что backend настроен с правильными CORS заголовками:

```python
# backend/eusrr_backend/settings.py
CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://localhost",
]
```

### 401 Unauthorized

- Проверьте, что токен действителен
- Убедитесь, что backend запущен
- Проверьте переменные окружения

### Ошибка сети

- Проверьте, что backend доступен
- Проверьте URL в `NEXT_PUBLIC_API_URL`
- Проверьте docker network, если используете docker-compose

---

**Дата создания**: 19 февраля 2026
**Версия**: 1.0
