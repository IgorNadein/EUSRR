# Migration Guide: ChatController → ChatControllerV2

**Дата миграции:** 13 января 2026  
**Статус:** ✅ Завершена  
**Версия:** 2.0.0

---

## 📋 Содержание

1. [Обзор изменений](#обзор-изменений)
2. [Breaking Changes](#breaking-changes)
3. [Пошаговая миграция](#пошаговая-миграция)
4. [Автоматическая миграция](#автоматическая-миграция)
5. [Новые возможности](#новые-возможности)
6. [FAQ](#faq)

---

## 🎯 Обзор изменений

### Что изменилось?

**V2 теперь является основной версией!** Старая версия переименована в Legacy.

```javascript
// ❌ СТАРЫЙ импорт (больше не работает):
import { ChatController } from './chat/index.js';

// ✅ НОВЫЙ импорт (V2 по умолчанию):
import { ChatController } from './chat/index.js'; // Это V2!

// Если нужна старая версия:
import { ChatControllerLegacy } from './chat/index.js';
```

### Основные улучшения V2:

- ✅ **Умный автоскролл** - как в Telegram
- ✅ **Индикатор новых сообщений** - с счетчиком
- ✅ **Batch операции** - 3x быстрее загрузка
- ✅ **Retry логика** - устойчивость к сбоям
- ✅ **AbortController** - отмена запросов
- ✅ **Централизованная конфигурация** - все настройки в одном месте

---

## ⚠️ Breaking Changes

### 1. Приватные свойства

**Проблема:** V2 использует приватные свойства (с `_`)

```javascript
// ❌ НЕ РАБОТАЕТ в V2:
controller.newMessagesCount = 0;
controller.initialized = true;

// ✅ РАБОТАЕТ в V2:
controller._newMessagesCount = 0; // Приватное
controller._initialized = true;    // Приватное
```

**Решение:** Используйте `ChatControllerCompat` для обратной совместимости:

```javascript
import { ChatControllerCompat } from './utils/chatMigration.js';

const controller = new ChatControllerCompat(options);
controller.newMessagesCount = 0; // Работает!
```

### 2. Опции конструктора

**Изменения:**

| Опция | V1 | V2 | Действие |
|-------|----|----|----------|
| `lastReadTimestamp` | ✅ | ❌ | Удалено |
| `lastReadMessageId` | ❌ | ✅ | Добавлено |

```javascript
// ❌ СТАРЫЙ код:
new ChatController({
    lastReadTimestamp: 1234567890
});

// ✅ НОВЫЙ код:
new ChatController({
    lastReadMessageId: 42 // ID вместо timestamp
});
```

### 3. События Store

**Приватизация:** Все обработчики теперь приватные:

```javascript
// ❌ НЕ РАБОТАЕТ:
controller._handleMessageAdded(data);

// ✅ РАБОТАЕТ (через Store):
controller.store.addMessage(message);
// → автоматически вызовет _onMessageAdded
```

---

## 🔄 Пошаговая миграция

### Вариант 1: Обновление импортов (рекомендуется)

**Шаг 1:** Обновите импорты в вашем коде

```javascript
// БЫЛО:
import ChatController from '../controllers/chatController.js';
import MessageStore from '../stores/messageStore.js';

// СТАЛО:
import { ChatController, MessageStore } from './chat/index.js';
// Это автоматически даст вам V2!
```

**Шаг 2:** Проверьте опции конструктора

```javascript
const controller = new ChatController({
    chatId: 1,
    scrollElement: document.getElementById('chat'),
    currentUserId: userId,
    containerId: 'chatScroll',
    // lastReadTimestamp: 123 // ❌ Удалите
    lastReadMessageId: 42     // ✅ Добавьте (опционально)
});
```

**Шаг 3:** Замените прямой доступ к свойствам

```javascript
// ❌ БЫЛО:
if (controller.initialized) { ... }
controller.newMessagesCount = 0;

// ✅ СТАЛО (вариант A - используйте методы):
if (controller._initialized) { ... }
controller._newMessagesCount = 0;

// ✅ СТАЛО (вариант B - используйте ChatControllerCompat):
import { ChatControllerCompat } from './utils/chatMigration.js';
const controller = new ChatControllerCompat(options);
// Теперь работает как раньше!
```

**Шаг 4:** Тестирование

```bash
# Запустите тесты
.venv/Scripts/python manage.py runserver

# Откройте в браузере:
http://localhost:8000/static/js/tests/chatTestsV2.html

# Запустите все тесты - должны пройти 18/18 (100%)
```

### Вариант 2: Автоматическая миграция существующих контроллеров

Если у вас уже работает старый контроллер, используйте `migrateToV2()`:

```javascript
import { migrateToV2 } from './utils/chatMigration.js';

// Старый контроллер работает
const oldController = new ChatControllerLegacy(options);
await oldController.init();

// Мигрируем на V2
const v2Controller = migrateToV2(oldController);
// Автоматически:
// - Сохраняет позицию скролла
// - Уничтожает старый контроллер
// - Создает V2 с теми же параметрами
// - Инициализирует и восстанавливает состояние
```

### Вариант 3: Постепенная миграция с Compatibility Layer

Используйте `ChatControllerCompat` для плавной миграции:

```javascript
import { ChatControllerCompat } from './utils/chatMigration.js';

// Создаем контроллер с compatibility layer
const controller = new ChatControllerCompat(options);

// Весь старый код работает без изменений!
controller.newMessagesCount = 0;       // Работает
controller.initialized = true;         // Работает
controller._dispatchEvent('test', {}); // Работает

// + Все новые фичи V2 доступны!
```

---

## 🤖 Автоматическая миграция

### Скрипт для обновления imports

Создайте файл `migrate-imports.sh`:

```bash
#!/bin/bash

# Замена старых импортов на новые
find backend/static/js -name "*.js" -type f -exec sed -i \
  's/import ChatController from.*chatController\.js/import { ChatController } from ".\/chat\/index.js"/g' {} +

find backend/static/js -name "*.js" -type f -exec sed -i \
  's/import MessageStore from.*messageStore\.js/import { MessageStore } from ".\/chat\/index.js"/g' {} +

echo "✅ Импорты обновлены!"
```

Запуск:

```bash
chmod +x migrate-imports.sh
./migrate-imports.sh
```

---

## ✨ Новые возможности V2

### 1. Умный автоскролл

**Поведение:**
- Свое сообщение → всегда скроллит вниз
- Чужое + внизу → скроллит (активно читаем)
- Чужое + история → показывает индикатор "N новых сообщений"

**Настройка:**

```javascript
import { AUTOSCROLL_CONFIG } from './chat/index.js';

// Кастомизация (опционально):
AUTOSCROLL_CONFIG.SMOOTH_SCROLL_FOR_OWN = true; // Плавный скролл
AUTOSCROLL_CONFIG.SHOW_ANIMATION_DURATION = 500; // Анимация показа
```

### 2. Централизованная конфигурация

```javascript
import { 
    LOADER_CONFIG, 
    SCROLL_CONFIG, 
    AUTOSCROLL_CONFIG 
} from './chat/index.js';

// Все настройки в одном месте!
LOADER_CONFIG.MAX_RETRIES = 5;
SCROLL_CONFIG.BOTTOM_THRESHOLD = 150;
AUTOSCROLL_CONFIG.SMOOTH_SCROLL_ON_CLICK = false;
```

### 3. Batch операции

```javascript
// V2 автоматически батчит уведомления
const messages = [...]; // 100 сообщений
store.addMessages(messages);
// → Одно событие вместо 100!
// → 3x быстрее
```

### 4. Retry логика

```javascript
// V2 автоматически переподключается при сбоях
loader.loadInitial(chatId); 
// При ошибке:
// - Попытка 1: сразу
// - Попытка 2: через 1 сек
// - Попытка 3: через 2 сек
// - Попытка 4: через 4 сек
// Exponential backoff!
```

### 5. Отмена запросов

```javascript
// V2 автоматически отменяет старые запросы
loader.loadInitial(1); // Запрос 1
loader.loadInitial(1); // Запрос 2
// → Запрос 1 автоматически отменен (AbortController)
// → Нет "race condition"
```

---

## ❓ FAQ

### Q: Могу ли я использовать старую версию?

**A:** Да, она доступна как `ChatControllerLegacy`:

```javascript
import { ChatControllerLegacy } from './chat/index.js';
const controller = new ChatControllerLegacy(options);
```

Но рекомендуется мигрировать на V2 для получения новых фичей и оптимизаций.

### Q: Как проверить какая версия используется?

**A:** Используйте утилиты миграции:

```javascript
import { getControllerVersion } from './utils/chatMigration.js';

const version = getControllerVersion(controller);
console.log(version); // 'v2' | 'legacy' | 'unknown'
```

### Q: Тесты не проходят после миграции?

**A:** Проверьте:

1. Обновили ли импорты в тестах?
2. Используете ли приватные свойства (`_newMessagesCount`)?
3. Запустите `chatTestsV2.html` для проверки V2

### Q: Как откатиться на старую версию?

**A:** Замените импорты:

```javascript
// ❌ Убрать:
import { ChatController } from './chat/index.js';

// ✅ Добавить:
import { ChatControllerLegacy as ChatController } from './chat/index.js';
```

### Q: Когда удалят Legacy версию?

**A:** Планируется удаление через 6 месяцев (июль 2026), после полной стабилизации V2.

---

## 📊 Чеклист миграции

- [ ] Обновлены импорты на `{ ChatController } from './chat/index.js'`
- [ ] Заменен `lastReadTimestamp` → `lastReadMessageId` (если использовался)
- [ ] Приватные свойства доступны через `_` или используется `ChatControllerCompat`
- [ ] Тесты пройдены (18/18 для smart autoscroll)
- [ ] Production протестирован
- [ ] Legacy код помечен для будущего удаления

---

## 🆘 Поддержка

Если возникли проблемы с миграцией:

1. Проверьте [V2_REFACTORING_EVALUATION.md](../../docs/reports/V2_REFACTORING_EVALUATION.md)
2. Запустите тесты: http://localhost:8000/static/js/tests/chatTestsV2.html
3. Используйте `ChatControllerCompat` для compatibility layer

---

**Успешной миграции! 🚀**
