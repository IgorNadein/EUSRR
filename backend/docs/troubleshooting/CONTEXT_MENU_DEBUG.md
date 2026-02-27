# Отладка контекстного меню сообщений

## Обзор

В файл `backend/static/js/components/messageContextMenu.js` добавлена подробная отладка для всех методов, которые обновляют DOM.

## Добавленные логи

### 1. Инициализация и подключение к сообщениям

**Constructor:**
- `[MessageContextMenu] Constructor called` - вызов конструктора с конфигом

**attachToExistingMessages():**
- `[MessageContextMenu] Attaching to existing messages in: {containerId}` - начало поиска существующих сообщений
- `[MessageContextMenu] Found X messages` - количество найденных сообщений

**observeNewMessages():**
- `[MessageContextMenu] Setting up MutationObserver` - установка наблюдателя
- `[MessageContextMenu] New message detected: {messageId}` - обнаружено новое сообщение
- `[MessageContextMenu] New message in batch: {messageId}` - сообщения в пакете (загрузка истории)

**attachToMessage():**
- `[MessageContextMenu] attachToMessage called:` + детали (messageId, authorId, isOwn, alreadyAttached)
- `[MessageContextMenu] Contextmenu listener attached to message: {messageId}` - обработчик правого клика подключен
- `[MessageContextMenu] All event listeners attached to message: {messageId}` - все обработчики подключены

### 2. События пользователя

**Правый клик (contextmenu):**
- `[MessageContextMenu] *** CONTEXTMENU EVENT FIRED ***` - сработал правый клик
- `[MessageContextMenu] Event details:` + координаты, target, messageId

**Touch события (мобилка):**
- `[MessageContextMenu] Touchstart event on message: {messageId}` - начало касания
- `[MessageContextMenu] Long press triggered on message: {messageId}` - долгое нажатие сработало
- `[MessageContextMenu] Touch moved, cancelling long press` - палец двигается, отмена
- `[MessageContextMenu] Touch ended` - касание завершено
- `[MessageContextMenu] Touch cancelled` - касание отменено

### 3. Создание и показ меню

**showMenu():**
- `[MessageContextMenu] showMenu called:` + детали (messageId, isOwn, координаты)
- `[MessageContextMenu] Creating menu...` - создание меню
- `[MessageContextMenu] Menu created, appending to body` - меню создано
- `[MessageContextMenu] Menu appended to DOM` - меню добавлено в DOM
- `[MessageContextMenu] Adding highlight to message` - добавление подсветки
- `[MessageContextMenu] Positioning menu` - позиционирование
- `[MessageContextMenu] Adding show class for animation` - анимация появления

**createMenu():**
- `[MessageContextMenu] createMenu:` + (messageId, isOwn)
- `[MessageContextMenu] Menu element created with class: {className}`
- `[MessageContextMenu] Creating reactions HTML with X emojis`
- `[MessageContextMenu] Setting innerHTML...`
- `[MessageContextMenu] innerHTML set successfully`
- `[MessageContextMenu] Attaching click handler to menu`
- `[MessageContextMenu] Click outside action button` - клик не по кнопке
- `[MessageContextMenu] Action button clicked: {action} {emoji}` - клик по кнопке
- `[MessageContextMenu] Menu fully constructed`

**positionMenu():**
- `[MessageContextMenu] positionMenu called:` + координаты
- `[MessageContextMenu] Menu dimensions:` + размеры и viewport
- `[MessageContextMenu] Adjusted left to prevent overflow` - корректировка позиции
- `[MessageContextMenu] Adjusted top to prevent bottom overflow` - корректировка
- `[MessageContextMenu] Final position:` + финальные координаты

### 4. Действия с сообщениями

**handleReply():**
- `[MessageContextMenu] handleReply called`
- `[MessageContextMenu] Bubble not found in message element` - warning
- `[MessageContextMenu] Reply data:` + (messageId, authorName, messageTextLength)
- `[MessageContextMenu] Using chatFormManager.setModeToReply`
- `[MessageContextMenu] chatFormManager not available, using fallback` - warning
- `[MessageContextMenu] Textarea #id_content not found` - error

**handleEdit():**
- `[MessageContextMenu] handleEdit called`
- `[MessageContextMenu] Bubble not found in message element` - warning
- `[MessageContextMenu] Edit data:` + (messageId, messageTextLength)
- `[MessageContextMenu] Using chatFormManager.setModeToEdit`
- `[MessageContextMenu] chatFormManager not available, using fallback` - warning
- `[MessageContextMenu] Textarea #id_content not found` - error

### 5. Закрытие и очистка

**removeHighlight():**
- `[MessageContextMenu] Removing highlight from message: {messageId}` - удаление подсветки
- `[MessageContextMenu] Highlight removed` - подсветка удалена
- `[MessageContextMenu] No highlighted message to remove` - нечего удалять

**closeMenu():**
- `[MessageContextMenu] closeMenu: no active menu` - нет активного меню
- `[MessageContextMenu] Closing menu` - закрытие меню
- `[MessageContextMenu] Removing show class for fade out` - анимация скрытия
- `[MessageContextMenu] Removing menu from DOM` - удаление из DOM

**showToast():**
- `[MessageContextMenu] showToast: {message}` - показ уведомления
- `[MessageContextMenu] Toast created, appending to body` - toast создан
- `[MessageContextMenu] Adding show class to toast` - анимация появления
- `[MessageContextMenu] Removing show class from toast` - анимация скрытия
- `[MessageContextMenu] Removing toast from DOM` - удаление toast

## Как использовать для диагностики

### Проблема: Контекстное меню не появляется

1. Откройте DevTools Console
2. Обновите страницу чата
3. Проверьте логи инициализации:
   ```
   [MessageContextMenu] Constructor called
   [MessageContextMenu] Found X messages
   [MessageContextMenu] Setting up MutationObserver
   ```

4. Кликните правой кнопкой по сообщению
5. Должны появиться логи:
   ```
   [MessageContextMenu] *** CONTEXTMENU EVENT FIRED ***
   [MessageContextMenu] Event details: {...}
   [MessageContextMenu] showMenu called: {...}
   ```

6. Если лог `CONTEXTMENU EVENT FIRED` не появляется - проблема в подключении обработчиков
7. Если появляется, но меню не показывается - проблема в создании/позиционировании

### Проблема: Меню не подключается к новым сообщениям

1. Отправьте новое сообщение
2. Должны появиться логи:
   ```
   [MessageContextMenu] New message detected: {messageId}
   [MessageContextMenu] attachToMessage called: {...}
   [MessageContextMenu] All event listeners attached to message: {messageId}
   ```

3. Если логи не появляются - MutationObserver не сработал
4. Проверьте, что контейнер `#chatScroll` существует

### Проблема: Действия (Reply/Edit) не работают

1. Кликните правой кнопкой по сообщению
2. Выберите "Ответить" или "Редактировать"
3. Проверьте логи:
   ```
   [MessageContextMenu] Action button clicked: reply
   [MessageContextMenu] handleReply called
   [MessageContextMenu] Using chatFormManager.setModeToReply
   ```

4. Если видите `chatFormManager not available, using fallback` - модуль не инициализирован
5. Проверьте, что `window.chatFormManager` доступен

## Удаление отладки для продакшна

Когда всё заработает, можно удалить `console.log` вызовы или заменить их на debug-флаг:

```javascript
constructor(config = {}) {
    this.debug = config.debug || false;
    // ...
}

log(...args) {
    if (this.debug) {
        console.log('[MessageContextMenu]', ...args);
    }
}
```

Затем использовать: `this.log('Message', data)` вместо `console.log('[MessageContextMenu] Message', data)`
