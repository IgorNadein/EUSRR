# 🚀 Запуск EUSRR Frontend + Backend

## ✅ Что уже сделано

- ✅ React frontend с Refine.dev создан
- ✅ Подключение к Django REST API настроено
- ✅ JWT авторизация реализована
- ✅ Создана страница списка сотрудников
- ✅ Настроены ресурсы для всех модулей

## 📋 Следующие шаги

### 1. Установить CORS на Django Backend

```bash
cd backend
.venv/Scripts/pip install django-cors-headers
```

### 1.5. Проверить что Daphne установлен

```bash
cd backend
.venv/Scripts/pip show daphne
```

Если Daphne не установлен:
```bash
.venv/Scripts/pip install daphne
```

Добавить в `backend/eusrr_backend/settings.py`:

```python
INSTALLED_APPS = [
    "daphne",
    "channels",
    "corsheaders",  # ← ДОБАВИТЬ
    # ...остальное...
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",  # ← ДОБАВИТЬ ВТОРЫМ!
    # ...остальное...
]

# В конец файла:
CORS_ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]
CORS_ALLOW_CREDENTIALS = True
```

**Полная инструкция:** [docs/guides/DJANGO_CORS_SETUP.md](../../docs/guides/DJANGO_CORS_SETUP.md)

### 2. Установить зависимости frontend

```bash
cd frontend
npm install
```

### 3. Запустить оба сервера

**⚠️ ВАЖНО: Для WebSocket используйте Daphne вместо стандартного Django сервера!**

**Terminal 1 - Django (с WebSocket на Daphne):**
```bash
cd backend
.venv/Scripts/daphne -b 0.0.0.0 -p 9000 eusrr_backend.asgi:application
```

Или используйте `runserver` для HTTP (без WebSocket):
```bash
cd backend
.venv/Scripts/python manage.py runserver 8000
```

**Terminal 2 - React:**
```bash
cd frontend
npm run dev
```

### 4. Открыть приложение

Откройте в браузере: **http://localhost:5173**

## 🔍 Проверка WebSocket подключения

1. Откройте **DevTools** (F12) → **Console**
2. Ищите сообщение `🔄 Подключение к WebSocket: ws://localhost:9000/ws/...`
3. Если ошибка `❌ WebSocket error: {}`, проверьте:
   - ✅ Backend запущен через Daphne (не через runserver)
   - ✅ PORT 9000 доступен (не занят другой программой)
   - ✅ JWT токен сохранен в localStorage
   - ✅ В файле `.env.local` стоит `NEXT_PUBLIC_WS_URL=ws://localhost:9000`

## 🔐 Тестовая авторизация

Используйте существующего пользователя из вашей БД:

```
Email: ваш_email@example.com
Password: ваш_пароль
```

После входа токен автоматически сохранится в `localStorage` и будет использован для WebSocket аутентификации.

## 📁 Структура страниц

Сейчас доступно:
- ✅ `/employees` - Список сотрудников (работает!)
- ⏳ `/departments` - TODO
- ⏳ `/documents` - TODO
- ⏳ `/requests` - TODO
- ⏳ `/events` - TODO
- ⏳ `/feed` - TODO
- ⏳ `/chats` - TODO

## 🛠️ Разработка

### Создание новой страницы

Например, для документов:

```bash
mkdir -p src/pages/documents
touch src/pages/documents/{list,create,edit,show}.tsx
touch src/pages/documents/index.ts
```

### Добавление маршрута

В `src/App.tsx` добавить:

```typescript
<Route path="/documents">
  <Route index element={<DocumentList />} />
  <Route path="create" element={<DocumentCreate />} />
  <Route path="edit/:id" element={<DocumentEdit />} />
  <Route path="show/:id" element={<DocumentShow />} />
</Route>
```

## 🐛 Проблемы?

### CORS ошибки
- Проверьте что `django-cors-headers` установлен
- Убедитесь что middleware добавлен правильно
- Перезапустите Django сервер

### 401 Unauthorized
- Проверьте что пользователь существует в БД
- Проверьте endpoint: `http://localhost:8000/api/auth/token/`

### WebSocket error: {}
**Это самая частая ошибка!** Решение:

1. **Проверьте что backend запущен через Daphne:**
   ```bash
   cd backend
   .venv/Scripts/daphne -b 0.0.0.0 -p 9000 eusrr_backend.asgi:application
   ```

2. **НЕ используйте `python manage.py runserver`** - это не поддерживает WebSocket!

3. **Убедитесь что .env.local имеет правильный URL:**
   ```dotenv
   NEXT_PUBLIC_WS_URL=ws://localhost:9000
   NEXT_PUBLIC_BACKEND_URL=http://localhost:9000
   ```

4. **Проверьте в DevTools → Network → WS:**
   - Введите фильтр `ws` чтобы найти WebSocket подключение
   - Если соединение **101 Switching Protocols** - всё работает ✅
   - Если ошибка **Failed** - backend не запущен через Daphne ❌

5. **Проверьте порт 9000:**
   ```bash
   # Windows - проверить какой процесс занимает порт
   netstat -ano | findstr :9000
   
   # Если занято - убейте процесс или используйте другой порт
   ```

### Страница не загружается
- Убедитесь что оба сервера запущены
- Проверьте `.env.local` файл в frontend
- Откройте DevTools → Network и посмотрите статусы запросов

## 📚 Документация

- Frontend README: [frontend/README.md](README.md)
- Django CORS: [docs/guides/DJANGO_CORS_SETUP.md](../../docs/guides/DJANGO_CORS_SETUP.md)
- **API v2 Migration**: [docs/guides/API_V2_MIGRATION.md](../../docs/guides/API_V2_MIGRATION.md)
- Refine Docs: https://refine.dev/docs/

## 🎯 Следующие задачи

1. Создать endpoint `/api/v2/employees/me/` для получения текущего пользователя
2. Добавить страницы для остальных модулей (documents, requests, etc.)
3. Добавить UI библиотеку (Ant Design / Material-UI)
4. Интегрировать WebSocket для чата
5. Добавить тесты

---

**Готово! Теперь можно разрабатывать! 🚀**
