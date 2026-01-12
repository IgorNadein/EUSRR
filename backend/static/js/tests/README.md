# 🧪 Chat System Tests

Комплексная система тестирования для чата EUSRR. Запускается прямо в браузере без дополнительных инструментов.

## ⚡ Быстрый старт

### Вариант 1: HTML интерфейс (Рекомендуется)

Откройте в браузере:
```
http://localhost:8000/static/js/tests/runTests.html
```

Нажмите кнопку "🚀 Запустить все тесты"

### Вариант 2: Консоль браузера

На странице чата откройте консоль (F12) и выполните:

```javascript
// Загрузить тесты
const script = document.createElement('script');
script.src = '/static/js/tests/chatTests.js';
script.type = 'module';
document.head.appendChild(script);

// Запустить все тесты
await window.ChatTests.runAll()

// Или отдельный модуль
await window.ChatTests.testMessageStore()
```

## 📦 Доступные тесты

```javascript
window.ChatTests.runAll()              // Все тесты
window.ChatTests.testMessageStore()    // Хранилище сообщений
window.ChatTests.testMessageLoader()   // Загрузчик сообщений
window.ChatTests.testScrollManager()   // Менеджер скролла
window.ChatTests.testMessageRenderer() // Рендерер сообщений
window.ChatTests.testChatController()  // Контроллер чата
window.ChatTests.testIntegration()     // Интеграционные тесты
window.ChatTests.testPerformance()     // Тесты производительности
```

## 📊 Что тестируется?

- ✅ **MessageStore** - 12 тестов (добавление, обновление, удаление, дубликаты, оптимистичные)
- ✅ **MessageLoader** - 9 тестов (загрузка, WebSocket, состояния)
- ✅ **ScrollManager** - 5 тестов (скролл, сохранение позиции, IntersectionObserver)
- ✅ **MessageRenderer** - 6 тестов (рендеринг, обновление, удаление)
- ✅ **ChatController** - 5 тестов (инициализация, методы, события)
- ✅ **Integration** - 4 теста (полный цикл, множественные сообщения, оптимистичная отправка)
- ✅ **Performance** - 4 теста (1000 сообщений, поиск, рендеринг, обновления)

**Всего: ~45+ тестов**

## 📈 Пример результата

```
🏁 ИТОГОВЫЕ РЕЗУЛЬТАТЫ
============================================================
Всего тестов: 45
✅ Успешно: 45
❌ Провалено: 0
📈 Процент успеха: 100.0%
============================================================
```

## 📚 Полная документация

См. [CHAT_TESTS_GUIDE.md](./CHAT_TESTS_GUIDE.md)

## 🎯 Использование

### Перед коммитом
```javascript
const results = await window.ChatTests.runAll()
console.log(`Ready to commit: ${results.failed === 0}`)
```

### После изменений
```javascript
// Изменили MessageStore?
await window.ChatTests.testMessageStore()

// Изменили рендеринг?
await window.ChatTests.testMessageRenderer()
```

### Проверка производительности
```javascript
await window.ChatTests.testPerformance()
```

---

**Документация:** [CHAT_TESTS_GUIDE.md](./CHAT_TESTS_GUIDE.md)
