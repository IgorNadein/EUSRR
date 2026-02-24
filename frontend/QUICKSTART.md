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

**Terminal 1 - Django:**
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

## 🔐 Тестовая авторизация

Используйте существующего пользователя из вашей БД:

```
Email: ваш_email@example.com
Password: ваш_пароль
```

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

### Страница не загружается
- Убедитесь что оба сервера запущены
- Проверьте `.env` файл в frontend
- Откройте DevTools → Network

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
