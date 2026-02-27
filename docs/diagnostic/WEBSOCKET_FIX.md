# 🔧 Исправление WebSocket ошибки: "❌ WebSocket error: {}"

## Проблема

При открытии чата в браузере видна ошибка:
```
❌ WebSocket error: {}
```

## Причины

WebSocket ошибка `{}` обычно связана с одной из этих проблем:

| Причина | Решение |
|---------|---------|
| **Backend запущен через `runserver`** | Используйте **Daphne** для WebSocket |
| **PORT 9000 занят** | Проверьте процессы или используйте другой порт |
| **Неправильный URL в .env** | Убедитесь что используется `.env.local` |
| **JWT токен не сохранен** | Выполните вход в систему |
| **Frontend и Backend на разных версиях** | Синхронизируйте код |

## ✅ Пошаговое решение

### Шаг 1: Остановите текущий backend
```bash
# Если backend запущен, нажмите Ctrl+C в терминале
```

### Шаг 2: Запустите backend через Daphne

```bash
cd backend
.venv/Scripts/daphne -b 0.0.0.0 -p 9000 eusrr_backend.asgi:application
```

**Ожидаемый вывод:**
```
Starting server process [PID]
HTTP/2 support not enabled
Uvicorn running on http://0.0.0.0:9000
```

### Шаг 3: Убедитесь что .env.local правильный

Проверьте файл `frontend/.env.local`:
```dotenv
# ✅ ПРАВИЛЬНО (для локальной разработки)
NEXT_PUBLIC_WS_URL=ws://localhost:9000
NEXT_PUBLIC_BACKEND_URL=http://localhost:9000
```

**НЕ используйте:**
```dotenv
# ❌ НЕПРАВИЛЬНО (production URL)
NEXT_PUBLIC_WS_URL=wss://corp.robotail.pro
```

### Шаг 4: Перезагрузите фронтенд

```bash
cd frontend
npm run dev
```

Перезагрузите браузер: `Ctrl+R` или `F5`

### Шаг 5: Проверьте WebSocket подключение

Откройте **DevTools** (F12) → **Console** окно и ищите:

**✅ Если видите:**
```
🔄 Подключение к WebSocket: ws://localhost:9000/ws/?token=...
✅ WebSocket connected!
```
→ **Всё работает!**

**❌ Если видите ошибку:**
```
❌ WebSocket error: {}
```
→ Продолжайте с Шага 6

### Шаг 6: Проверьте порт 9000

Проверьте что процесс слушает на порту 9000:

**Windows - PowerShell (администратор):**
```powershell
# Проверить какие процессы используют порт 9000
netstat -ano | findstr :9000

# Пример вывода:
# TCP  0.0.0.0:9000  0.0.0.0:0  LISTENING  28904

# Если что-то там слушает, проверьте что это Daphne
tasklist | findstr 28904
```

Если порт занят другим процессом:
```bash
# Убить процесс в PowerShell
taskkill /PID 28904 /F

# Или используйте другой порт
.venv/Scripts/daphne -b 0.0.0.0 -p 9001 eusrr_backend.asgi:application

# И обновите .env.local
NEXT_PUBLIC_WS_URL=ws://localhost:9001
```

### Шаг 7: Проверьте Network в DevTools

1. Откройте **DevTools** → **Network** вкладка
2. В фильтре напишите: `ws`
3. Откройте чат и ищите подключение `ws://localhost:9000/ws/`

**✅ Если видите:**
```
ws   Status: 101 Switching Protocols  [WebSocket connected]
```

**❌ Если видите:**
```
ws   Status: Failed  [или ConnectError]
```
→ Backend неправильно запущен

## 🔄 Полный скрипт для переустановки

```bash
# 1. Перейдите в backend
cd backend

# 2. Установите dependencies если нужно
.venv/Scripts/pip install -r requirements.txt

# 3. Запустите Daphne
.venv/Scripts/daphne -b 0.0.0.0 -p 9000 eusrr_backend.asgi:application

# В другом терминале:

# 4. Перейдите в frontend
cd frontend

# 5. Установите если нужно
npm install

# 6. Запустите dev server
npm run dev

# 7. Откройте браузер на http://localhost:5173
```

## 📋 Чек-лист для диагностики

- [ ] Backend запущен через **Daphne** (не `runserver`)
- [ ] PORT **9000** свободен и доступен
- [ ] `.env.local` использует `ws://localhost:9000`
- [ ] JWT токен сохранен в localStorage (пользователь залогирован)
- [ ] Frontend запущен на `http://localhost:5173`
- [ ] В DevTools → Console видно `🔄 Подключение к WebSocket`
- [ ] В DevTools → Network видно WebSocket с статусом **101**

## 🚨 Если ничего не помогает

1. **Очистите cache браузера**
   - F12 → Application → Clear Site Data → ✓ Cookies, ✓ Cache

2. **Удалите node_modules и переустановите**
   ```bash
   cd frontend
   rm -r node_modules package-lock.json
   npm install
   npm run dev
   ```

3. **Проверьте logs в backend**
   - В терминале где запущен Daphne должны быть logs подключений
   - Если их нет - frontend не отправляет запрос

4. **Обновите код из Git**
   ```bash
   git pull origin main
   npm install
   .venv/Scripts/pip install -r requirements.txt
   ```

## 📞 Если проблема не решена

Создайте issue с информацией:
- Output из DevTools Console
- Output из Daphne терминала
- Содержимое `.env.local`
- Результат: `netstat -ano | findstr :9000` (Windows)
