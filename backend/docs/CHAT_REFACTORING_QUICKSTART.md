# Chat Handler Refactoring - Quick Start

> **Статус**: 🔴 Требуется отдельная сессия (2-3 часа)  
> **Приоритет**: Средний (после завершения можно переходить к Фазе 5)  
> **Детальный план**: [CHAT_REFACTORING_SESSION.md](./CHAT_REFACTORING_SESSION.md)

## Что нужно сделать

Извлечь **521 строку** встроенного JavaScript из `templates/base.html` в **6 переиспользуемых модулей**.

## Структура

### Текущее состояние (base.html)
```
📄 base.html
├── Avatar Map (6 строк) - инициализация карты аватаров
├── Chat Detail Handler (186 строк) - автоскролл, textarea, отметка прочитанного
├── WebSocket Chat (161 строка) - реалтайм сообщения
├── Chat List Filter (42 строки) - поиск и фильтрация
├── Chat List Realtime (62 строки) - обновление списка через WS
└── Global Badge Updater (60 строк) - счетчик непрочитанных
```

### Целевая структура
```
📁 static/js/components/chat/
├── chatAvatars.js (простой, 5 минут)
├── chatListFilter.js (простой, 15 минут)
├── chatBadgeUpdater.js (средний, 30 минут)
├── chatListRealtime.js (средний, 30 минут)
├── chatDetailHandler.js (сложный, 60 минут) ⚠️
└── chatWebSocket.js (сложный, 60 минут) ⚠️
```

## Порядок работы

1. **chatAvatars.js** - быстрая победа ✅
2. **chatListFilter.js** - независимый модуль
3. **chatBadgeUpdater.js** - обновление бейджа
4. **chatListRealtime.js** - WebSocket для списка
5. **chatDetailHandler.js** - логика детального чата
6. **chatWebSocket.js** - WebSocket для сообщений

## Зависимости

```
chatAvatars.js
    ↓
chatWebSocket.js ← chatDetailHandler.js
    ↓                   ↓
chatListRealtime.js → chatBadgeUpdater.js
    ↓
chatListFilter.js
```

## Результат

**До**: 521 строка встроенного JS  
**После**: ~40 строк инициализации + 6 модулей  
**Сокращение**: 92% 🎉

## Начало работы

1. Прочитать [CHAT_REFACTORING_SESSION.md](./CHAT_REFACTORING_SESSION.md)
2. Создать директорию `static/js/components/chat/`
3. Начать с простых модулей (chatAvatars, chatListFilter)
4. Тестировать каждый модуль после создания
5. Обновить base.html в конце

## Чеклист тестирования

- [ ] Открытие детального чата → автоскролл работает
- [ ] Отправка сообщения → появляется в реальном времени
- [ ] Получение сообщения → обновляется счетчик
- [ ] Поиск в списке чатов → фильтрация работает
- [ ] Новое сообщение → список пересортируется
- [ ] Прочтение чата → бейдж обновляется

## Потенциальные проблемы

⚠️ **Порядок инициализации**: chatWebSocket зависит от chatDetailHandler  
✅ **Решение**: передавать chatDetail как параметр

⚠️ **Django context**: chatId, meId нужны из шаблона  
✅ **Решение**: передавать через параметры инициализации

⚠️ **Обратная совместимость**: `window.__CHAT_MARK_READ__`  
✅ **Решение**: экспортировать в window

---

**См. также**: [Полный план рефакторинга](./CHAT_REFACTORING_SESSION.md)
