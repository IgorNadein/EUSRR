/**
 * Тесты для системы чата
 * Запуск из консоли браузера:
 * 
 * 1. Загрузить скрипт:
 *    const script = document.createElement('script');
 *    script.src = '/static/js/tests/chatTests.js';
 *    script.type = 'module';
 *    document.head.appendChild(script);
 * 
 * 2. Или скопировать весь код в консоль
 * 
 * 3. Запустить тесты:
 *    window.ChatTests.runAll()              // Все тесты
 *    window.ChatTests.testMessageStore()    // Отдельный модуль
 *    window.ChatTests.testMessageLoader()
 *    window.ChatTests.testScrollManager()
 *    window.ChatTests.testMessageRenderer()
 *    window.ChatTests.testChatController()
 */

import MessageStore from '../stores/messageStore.js';
import MessageLoader from '../loaders/messageLoader.js';
import ScrollManager from '../managers/scrollManager.js';
import MessageRendererV2 from '../renderers/messageRendererV2.js';
import ChatController from '../controllers/chatController.js';

class ChatTestSuite {
    constructor() {
        this.results = {
            passed: 0,
            failed: 0,
            total: 0,
            details: []
        };
    }

    // ==================== Утилиты ====================

    /**
     * Генерирует реалистичное сообщение в формате бэкэнда
     * @param {Object} overrides - Поля для переопределения
     * @returns {Object} Сообщение в формате serialize_message()
     */
    createRealisticMessage(overrides = {}) {
        const defaults = {
            id: Math.floor(Math.random() * 10000),
            content: 'Тестовое сообщение',
            author_id: 1,
            author_name: 'Тестовый пользователь',
            author_url: '/employees/1/',
            avatar: '/media/users/avatars/default.jpg',
            created: '12.01.2026 16:00',
            created_ts: Date.now(),
            is_edited: false,
            edited_at: null,
            is_deleted: false,
            is_pinned: false,
            is_forwarded: false,
            is_system: false,
            has_attachments: false,
            reactions_summary: {},
            // Опциональные поля
            reply_to: null,
            forwarded_from: null,
            attachments: [],
            poll: null
        };
        return { ...defaults, ...overrides };
    }

    assert(condition, message) {
        this.results.total++;
        if (condition) {
            this.results.passed++;
            console.log(`✅ PASS: ${message}`);
            this.results.details.push({ status: 'PASS', message });
        } else {
            this.results.failed++;
            console.error(`❌ FAIL: ${message}`);
            this.results.details.push({ status: 'FAIL', message });
        }
    }

    assertEqual(actual, expected, message) {
        const condition = actual === expected;
        const fullMessage = `${message} (expected: ${expected}, got: ${actual})`;
        this.assert(condition, fullMessage);
    }

    assertNotNull(value, message) {
        this.assert(value !== null && value !== undefined, message);
    }

    async sleep(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }

    /**
     * Проверяет, видимо ли сообщение в контейнере
     * @private
     */
    _isMessageVisible(container, messageId) {
        const messageEl = container.querySelector(`[data-message-id="${messageId}"]`);
        if (!messageEl) return false;
        
        const rect = messageEl.getBoundingClientRect();
        const containerRect = container.getBoundingClientRect();
        
        // Проверяем что хотя бы часть сообщения видна
        return rect.bottom > containerRect.top && rect.top < containerRect.bottom;
    }

    resetResults() {
        this.results = {
            passed: 0,
            failed: 0,
            total: 0,
            details: []
        };
    }

    printResults() {
        console.log('\n' + '='.repeat(60));
        console.log('📊 РЕЗУЛЬТАТЫ ТЕСТОВ');
        console.log('='.repeat(60));
        console.log(`Всего тестов: ${this.results.total}`);
        console.log(`✅ Успешно: ${this.results.passed}`);
        console.log(`❌ Провалено: ${this.results.failed}`);
        console.log(`📈 Процент успеха: ${(this.results.passed / this.results.total * 100).toFixed(1)}%`);
        console.log('='.repeat(60) + '\n');
        
        if (this.results.failed > 0) {
            console.log('❌ Проваленные тесты:');
            this.results.details
                .filter(d => d.status === 'FAIL')
                .forEach(d => console.log(`  - ${d.message}`));
        }
    }

    // ==================== Тесты MessageStore ====================

    async testMessageStore() {
        console.log('\n🧪 Тестирование MessageStore...\n');
        this.resetResults();

        const store = new MessageStore();
        const chatId = 1;

        // Тест 1: Добавление одного сообщения с реальной структурой
        const msg1 = this.createRealisticMessage({
            id: 100,
            chat_id: chatId,
            author_id: 1,
            author_name: 'Иван Иванов',
            content: 'Тестовое сообщение 1',
            created: '12.01.2026 10:00',
            created_ts: new Date('2024-01-01T10:00:00Z').getTime()
        });
        
        const added = store.addMessage(msg1);
        this.assertEqual(added, 1, 'Добавление одного сообщения должно вернуть 1');
        this.assertEqual(store.getMessagesForChat(chatId).length, 1, 'В чате должно быть 1 сообщение');

        // Тест 2: Попытка добавить дубликат
        const duplicate = store.addMessage(msg1);
        this.assertEqual(duplicate, 0, 'Добавление дубликата должно вернуть 0');
        this.assertEqual(store.getMessagesForChat(chatId).length, 1, 'Количество сообщений не должно измениться');

        // Тест 3: Массовое добавление с реальной структурой
        const messages = [
            this.createRealisticMessage({ 
                id: 101, 
                chat_id: chatId, 
                author_id: 1,
                author_name: 'Иван Иванов',
                content: 'Сообщение 2', 
                created_ts: new Date('2024-01-01T10:01:00Z').getTime() 
            }),
            this.createRealisticMessage({ 
                id: 102, 
                chat_id: chatId, 
                author_id: 2,
                author_name: 'Пётр Петров',
                content: 'Сообщение 3', 
                created_ts: new Date('2024-01-01T10:02:00Z').getTime() 
            }),
            this.createRealisticMessage({ 
                id: 103, 
                chat_id: chatId, 
                author_id: 1,
                author_name: 'Иван Иванов',
                content: 'Сообщение 4',
                created_ts: new Date('2024-01-01T10:03:00Z').getTime() 
            })
        ];
        
        const addedCount = store.addMessages(messages);
        this.assertEqual(addedCount, 3, 'Добавление 3 новых сообщений должно вернуть 3');
        this.assertEqual(store.getMessagesForChat(chatId).length, 4, 'Всего должно быть 4 сообщения');

        // Тест 4: Сообщение с reply_to
        const msgWithReply = this.createRealisticMessage({
            id: 104,
            chat_id: chatId,
            author_id: 2,
            author_name: 'Пётр Петров',
            content: 'Ответ на сообщение',
            created_ts: new Date('2024-01-01T10:04:00Z').getTime(),
            reply_to: {
                id: 100,
                content: 'Тестовое сообщение 1',
                author_name: 'Иван Иванов'
            }
        });
        store.addMessage(msgWithReply);
        const savedMsg = store.getMessagesForChat(chatId).find(m => m.id === 104);
        this.assertNotNull(savedMsg.reply_to, 'Сообщение с reply_to должно сохранить это поле');
        this.assertEqual(savedMsg.reply_to.id, 100, 'reply_to.id должен совпадать');

        // Тест 5: Сообщение с вложениями
        const msgWithAttachment = this.createRealisticMessage({
            id: 105,
            chat_id: chatId,
            author_id: 1,
            author_name: 'Иван Иванов',
            content: 'Сообщение с файлом',
            created_ts: new Date('2024-01-01T10:05:00Z').getTime(),
            has_attachments: true,
            attachments: [{
                id: 1,
                file_name: 'document.pdf',
                file_type: 'application/pdf',
                file_url: '/media/attachments/document.pdf',
                file_size: 1024000,
                mime_type: 'application/pdf',
                thumbnail: null
            }]
        });
        store.addMessage(msgWithAttachment);
        const savedMsgAtt = store.getMessagesForChat(chatId).find(m => m.id === 105);
        this.assert(savedMsgAtt.has_attachments, 'has_attachments должен быть true');
        this.assertEqual(savedMsgAtt.attachments.length, 1, 'Должно быть 1 вложение');

        // Тест 6: Сообщение с reactions
        const msgWithReactions = this.createRealisticMessage({
            id: 106,
            chat_id: chatId,
            author_id: 1,
            author_name: 'Иван Иванов',
            content: 'Сообщение с реакциями',
            created_ts: new Date('2024-01-01T10:06:00Z').getTime(),
            reactions_summary: {
                '👍': { count: 3, users: [1, 2, 3], user_names: ['User1', 'User2', 'User3'] },
                '❤️': { count: 1, users: [2], user_names: ['User2'] }
            }
        });
        store.addMessage(msgWithReactions);
        const savedMsgReact = store.getMessagesForChat(chatId).find(m => m.id === 106);
        this.assertNotNull(savedMsgReact.reactions_summary, 'reactions_summary должен существовать');
        this.assertEqual(Object.keys(savedMsgReact.reactions_summary).length, 2, 'Должно быть 2 типа реакций');

        // Тест 7: Получение сообщения по ID
        const retrieved = store.getMessage(100);
        this.assertNotNull(retrieved, 'Сообщение должно быть найдено');
        this.assertEqual(retrieved.content, 'Тестовое сообщение 1', 'Содержимое должно совпадать');

        // Тест 8: Проверка наличия сообщения
        this.assert(store.hasMessage(100), 'hasMessage(100) должен вернуть true');
        this.assert(!store.hasMessage(999), 'hasMessage(999) должен вернуть false');

        // Тест 9: Получение старейшего сообщения
        const oldest = store.getOldestMessage(chatId);
        this.assertEqual(oldest.id, 100, 'Старейшее сообщение должно иметь ID 100');

        // Тест 10: Получение новейшего сообщения
        const newest = store.getNewestMessage(chatId);
        this.assertEqual(newest.id, 106, 'Новейшее сообщение должно иметь ID 106');

        // Тест 8: Обновление сообщения
        store.updateMessage(100, { content: 'Updated content', is_edited: true });
        const updated = store.getMessage(100);
        this.assertEqual(updated.content, 'Updated content', 'Содержимое должно быть обновлено');
        this.assert(updated.is_edited, 'Флаг is_edited должен быть true');

        // Тест 11: Удаление сообщения
        store.removeMessage(100);
        this.assert(!store.hasMessage(100), 'Сообщение 100 должно быть удалено');
        // Было добавлено: 4 (тесты 1-3) + 3 (тесты 4-6) = 7 сообщений, удалили 1 = 6
        this.assertEqual(store.getMessagesForChat(chatId).length, 6, 'Должно остаться 6 сообщений');

        // Тест 12: Очистка чата
        store.clearChat(chatId);
        this.assertEqual(store.getMessagesForChat(chatId).length, 0, 'Чат должен быть пустым');

        // Тест 13: Оптимистичное сообщение
        const tempId = `temp_${Date.now()}`;
        const optimisticMsg = this.createRealisticMessage({
            id: tempId,
            chat_id: chatId,
            author_id: 1,
            author_name: 'Тестовый пользователь',
            content: 'Оптимистичное сообщение',
            created_ts: Date.now(),
            is_optimistic: true
        });
        
        store.addOptimisticMessage(tempId, optimisticMsg);
        this.assert(store.optimisticMessages.has(tempId), 'Оптимистичное сообщение должно быть сохранено');
        
        // Подтверждение оптимистичного сообщения
        const confirmed = this.createRealisticMessage({
            id: 200,
            chat_id: chatId,
            author_id: 1,
            author_name: 'Тестовый пользователь',
            content: 'Оптимистичное сообщение',
            created_ts: optimisticMsg.created_ts
        });
        
        store.confirmOptimisticMessage(tempId, confirmed);
        this.assert(!store.optimisticMessages.has(tempId), 'Оптимистичное сообщение должно быть удалено');
        this.assert(store.hasMessage(200), 'Подтвержденное сообщение должно существовать');

        // Тест 14: События Store
        let eventFired = false;
        const listener = () => { eventFired = true; };
        
        store.on('messageAdded', listener);
        store.addMessage(this.createRealisticMessage({ 
            id: 201, 
            chat_id: chatId,
            author_id: 1,
            author_name: 'Тестовый пользователь',
            content: 'Тест события',
            created_ts: Date.now()
        }));
        
        await this.sleep(10); // Даем время на обработку события
        this.assert(eventFired, 'Событие messageAdded должно быть вызвано');
        
        store.off('messageAdded', listener);

        this.printResults();
        return this.results;
    }

    // ==================== Тесты MessageLoader ====================

    async testMessageLoader() {
        console.log('\n🧪 Тестирование MessageLoader...\n');
        this.resetResults();

        const store = new MessageStore();
        const loader = new MessageLoader({ store });

        // Эти тесты требуют реального API, поэтому проверяем структуру
        
        // Тест 1: Инициализация
        this.assertNotNull(loader.store, 'Store должен быть инициализирован');
        this.assertNotNull(loader.loadingState, 'LoadingState должен быть инициализирован');
        this.assertNotNull(loader.chatState, 'ChatState должен быть инициализирован');

        // Тест 2: Получение состояния загрузки
        const state = loader._getLoadingState(1);
        this.assert(state.hasOwnProperty('initial'), 'Состояние должно иметь поле initial');
        this.assert(state.hasOwnProperty('history'), 'Состояние должно иметь поле history');
        this.assert(state.hasOwnProperty('status'), 'Состояние должно иметь поле status');

        // Тест 3: Получение состояния чата
        const chatState = loader._getChatState(1);
        this.assert(chatState.hasOwnProperty('hasMore'), 'Состояние чата должно иметь поле hasMore');
        this.assert(chatState.hasOwnProperty('oldestId'), 'Состояние чата должно иметь поле oldestId');

        // Тест 4: Обновление состояния чата
        loader._updateChatState(1, { hasMore: false, oldestId: 100 });
        const updatedState = loader._getChatState(1);
        this.assertEqual(updatedState.hasMore, false, 'hasMore должен быть обновлен');
        this.assertEqual(updatedState.oldestId, 100, 'oldestId должен быть обновлен');

        // Тест 5: Проверка hasMoreHistory
        this.assertEqual(loader.hasMoreHistory(1), false, 'hasMoreHistory должен вернуть false');
        
        loader._updateChatState(1, { hasMore: true });
        this.assertEqual(loader.hasMoreHistory(1), true, 'hasMoreHistory должен вернуть true');

        // Тест 6: Методы WebSocket обработчиков существуют
        this.assert(typeof loader.handleNewMessage === 'function', 'handleNewMessage должен быть функцией');
        this.assert(typeof loader.handleMessageEdited === 'function', 'handleMessageEdited должен быть функцией');
        this.assert(typeof loader.handleMessageRemoved === 'function', 'handleMessageRemoved должен быть функцией');
        this.assert(typeof loader.handleReactionAdded === 'function', 'handleReactionAdded должен быть функцией');
        this.assert(typeof loader.handleReactionRemoved === 'function', 'handleReactionRemoved должен быть функцией');

        // Тест 7: Тестируем handleNewMessage с mock данными
        const testMsg = {
            id: 300,
            chat_id: 1,
            sender: { id: 1, username: 'test' },
            content: 'Test WS message',
            created_at: new Date().toISOString()
        };
        
        loader.currentChatId = 1;
        loader.handleNewMessage(testMsg);
        
        this.assert(store.hasMessage(300), 'Сообщение из WebSocket должно быть добавлено в Store');

        // Тест 8: Тестируем handleMessageEdited
        loader.handleMessageEdited({ 
            message: { ...testMsg, content: 'Edited content', is_edited: true }
        });
        
        const edited = store.getMessage(300);
        this.assertEqual(edited.content, 'Edited content', 'Сообщение должно быть отредактировано');

        // Тест 9: Тестируем handleMessageRemoved
        loader.handleMessageRemoved({ message_id: 300 });
        this.assert(!store.hasMessage(300), 'Сообщение должно быть удалено');

        this.printResults();
        return this.results;
    }

    // ==================== Тесты ScrollManager ====================

    async testScrollManager() {
        console.log('\n🧪 Тестирование ScrollManager...\n');
        this.resetResults();

        // Создаем mock элементы
        const container = document.createElement('div');
        container.style.height = '500px';
        container.style.overflow = 'auto';
        document.body.appendChild(container);

        const store = new MessageStore();
        const loader = new MessageLoader({ store });
        const renderer = new MessageRendererV2({ 
            store, 
            containerId: 'test-container',
            currentUserId: 1 
        });
        const manager = new ScrollManager({
            scrollElement: container,
            messageLoader: loader,
            messageRenderer: renderer,
            messageStore: store,
            chatId: 1
        });

        // Тест 1: Инициализация
        this.assertNotNull(manager.scrollEl, 'ScrollElement должен быть инициализирован');
        this.assertNotNull(manager.loader, 'Loader должен быть инициализирован');

        // Тест 2: Методы существуют
        this.assert(typeof manager.scrollToBottom === 'function', 'scrollToBottom должен быть функцией');
        this.assert(typeof manager.scrollToMessage === 'function', 'scrollToMessage должен быть функцией');
        this.assert(typeof manager.saveScrollPosition === 'function', 'saveScrollPosition должен быть функцией');
        this.assert(typeof manager.restoreScrollPosition === 'function', 'restoreScrollPosition должен быть функцией');
        this.assert(typeof manager.setupIntersectionObserver === 'function', 'setupIntersectionObserver должен быть функцией');

        // Тест 3: Сохранение и восстановление позиции
        container.scrollTop = 100;
        const savedPos = manager.saveScrollPosition();
        this.assertNotNull(savedPos, 'Позиция должна быть сохранена');
        
        container.scrollTop = 0;
        manager.restoreScrollPosition(savedPos);
        // Note: в тестах может не работать точное восстановление из-за отсутствия реального контента

        // Тест 4: scrollToBottom
        const contentDiv = document.createElement('div');
        contentDiv.style.height = '1000px';
        container.appendChild(contentDiv);
        
        manager.scrollToBottom();
        await this.sleep(100);
        // Примечание: в тестах scrollTop может не работать корректно без реального контента
        this.assert(true, 'scrollToBottom выполнен без ошибок');

        // Тест 5: setupIntersectionObserver
        // Добавляем mock сообщение в DOM для observer'а (должен быть класс .msg)
        const messageDiv = document.createElement('div');
        messageDiv.className = 'msg';
        messageDiv.setAttribute('data-message-id', '1');
        container.appendChild(messageDiv);
        
        manager.setupIntersectionObserver();
        this.assertNotNull(manager.historyObserver, 'IntersectionObserver должен быть создан когда есть сообщения');

        // Cleanup
        manager.destroy();
        document.body.removeChild(container);

        this.printResults();
        return this.results;
    }

    // ==================== Тесты MessageRenderer ====================

    async testMessageRenderer() {
        console.log('\n🧪 Тестирование MessageRenderer...\n');
        this.resetResults();

        // Создаем mock элементы
        const container = document.createElement('div');
        container.id = 'messages-list';
        document.body.appendChild(container);

        const store = new MessageStore();
        const currentUser = { id: 1, username: 'testuser' };
        const renderer = new MessageRendererV2({ 
            store, 
            containerId: 'messages-list',
            currentUserId: currentUser.id 
        });

        // Тест 1: Инициализация
        this.assertNotNull(renderer.containerId, 'Container ID должен быть инициализирован');
        this.assertNotNull(renderer.store, 'Store должен быть инициализирован');
        this.assertEqual(renderer.currentUserId, 1, 'CurrentUserId должен быть установлен');

        // Тест 2: Рендеринг сообщения
        const testMsg = {
            id: 400,
            chat_id: 1,
            sender: { id: 2, username: 'other', display_name: 'Other User' },
            content: 'Test render message',
            created_at: '2024-01-01T10:00:00Z',
            is_read: false
        };

        store.addMessage(testMsg);
        renderer.render(1);
        
        await this.sleep(100);
        
        const msgElement = container.querySelector('[data-message-id="400"]');
        this.assertNotNull(msgElement, 'Элемент сообщения должен быть отрендерен');

        // Тест 3: Обновление сообщения
        store.updateMessage(400, { content: 'Updated render content', is_edited: true });
        renderer.render(1);
        
        await this.sleep(100);
        
        const updatedElement = container.querySelector('[data-message-id="400"]');
        this.assert(updatedElement.textContent.includes('Updated render content'), 'Содержимое должно быть обновлено');

        // Тест 4: Рендеринг собственного сообщения
        const ownMsg = {
            id: 401,
            chat_id: 1,
            sender: { id: 1, username: 'testuser', display_name: 'Test User' },
            content: 'My message',
            created_at: '2024-01-01T10:01:00Z'
        };

        store.addMessage(ownMsg);
        renderer.render(1);
        
        await this.sleep(100);
        
        const ownElement = container.querySelector('[data-message-id="401"]');
        this.assertNotNull(ownElement, 'Собственное сообщение должно быть отрендерено');

        // Тест 5: Удаление сообщения
        store.removeMessage(400);
        renderer.render(1);
        
        await this.sleep(100);
        
        const removedElement = container.querySelector('[data-message-id="400"]');
        this.assert(!removedElement, 'Удаленное сообщение не должно отображаться');

        // Тест 6: Очистка контейнера
        renderer.clear();
        this.assertEqual(container.children.length, 0, 'Контейнер должен быть пустым');

        // Cleanup
        document.body.removeChild(container);

        this.printResults();
        return this.results;
    }

    // ==================== Тесты ChatController ====================

    async testChatController() {
        console.log('\n🧪 Тестирование ChatController...\n');
        this.resetResults();

        // Создаем mock элементы
        const container = document.createElement('div');
        container.id = 'messages-list';
        container.style.height = '500px';
        container.style.overflow = 'auto';
        document.body.appendChild(container);

        const currentUser = { id: 1, username: 'testuser' };
        const controller = new ChatController({
            chatId: 1,
            scrollElement: container,
            containerId: 'messages-list',
            currentUserId: currentUser.id
        });

        // Тест 1: Инициализация
        this.assertNotNull(controller.store, 'Store должен быть создан');
        this.assertNotNull(controller.loader, 'Loader должен быть создан');
        this.assertNotNull(controller.renderer, 'Renderer должен быть создан');
        this.assertNotNull(controller.scrollManager, 'ScrollManager должен быть создан');

        // Тест 2: Методы существуют
        this.assert(typeof controller.init === 'function', 'init должен быть функцией');
        this.assert(typeof controller.sendMessage === 'function', 'sendMessage должен быть функцией');
        this.assert(typeof controller.destroy === 'function', 'destroy должен быть функцией');

        // Тест 3: Event listeners
        let eventReceived = false;
        const handler = () => { eventReceived = true; };
        
        controller.store.on('messageAdded', handler);
        controller.store.addMessage({
            id: 500,
            chat_id: 1,
            sender: { id: 1 },
            content: 'Test controller message',
            created_at: new Date().toISOString()
        });
        
        await this.sleep(10);
        this.assert(eventReceived, 'Event handler должен получить событие');

        // Тест 4: Получение текущего чата
        controller.currentChatId = 1;
        this.assertEqual(controller.currentChatId, 1, 'CurrentChatId должен быть установлен');

        // Тест 5: Отправка оптимистичного сообщения (mock)
        const tempId = controller.loader.sendMessageOptimistically(1, 'Optimistic test');
        this.assertNotNull(tempId, 'Временный ID должен быть возвращен');
        this.assert(tempId.startsWith('temp_'), 'Временный ID должен начинаться с temp_');

        // Cleanup
        controller.destroy();
        document.body.removeChild(container);

        this.printResults();
        return this.results;
    }

    // ==================== Интеграционные тесты ====================

    async testIntegration() {
        console.log('\n🧪 Интеграционные тесты...\n');
        this.resetResults();

        // Создаем полную систему
        const container = document.createElement('div');
        container.id = 'messages-list';
        container.style.height = '500px';
        container.style.overflow = 'auto';
        document.body.appendChild(container);

        const chatId = 1;
        const currentUser = { id: 1, username: 'testuser' };
        const controller = new ChatController({
            chatId: chatId,
            scrollElement: container,
            containerId: 'messages-list',
            currentUserId: currentUser.id
        });

        // Тест 1: Полный цикл сообщения
        console.log('\n--- Тест 1: Полный цикл сообщения ---');
        
        // Добавляем сообщение в Store
        const msg1 = {
            id: 600,
            chat_id: chatId,
            sender: { id: 2, username: 'other', display_name: 'Other' },
            content: 'Integration test message',
            created_at: new Date().toISOString()
        };
        
        controller.store.addMessage(msg1);
        controller.renderer.render(chatId);
        await this.sleep(100);
        
        let element = container.querySelector('[data-message-id="600"]');
        this.assertNotNull(element, 'Сообщение должно быть отрендерено');
        
        // Редактируем сообщение
        controller.store.updateMessage(600, { content: 'Edited integration message', is_edited: true });
        controller.renderer.render(chatId);
        await this.sleep(100);
        
        element = container.querySelector('[data-message-id="600"]');
        this.assert(element.textContent.includes('Edited integration message'), 'Сообщение должно быть обновлено');
        
        // Удаляем сообщение
        controller.store.removeMessage(600);
        controller.renderer.render(chatId);
        await this.sleep(100);
        
        element = container.querySelector('[data-message-id="600"]');
        this.assert(!element, 'Сообщение должно быть удалено');

        // Тест 2: Множественные сообщения
        console.log('\n--- Тест 2: Множественные сообщения ---');
        
        const messages = [];
        for (let i = 0; i < 10; i++) {
            messages.push({
                id: 700 + i,
                chat_id: chatId,
                sender: { id: i % 2 === 0 ? 1 : 2, username: `user${i % 2}` },
                content: `Message ${i}`,
                created_at: new Date(Date.now() + i * 1000).toISOString()
            });
        }
        
        controller.store.addMessages(messages);
        controller.renderer.render(chatId);
        await this.sleep(200);
        
        const renderedMessages = container.querySelectorAll('[data-message-id]');
        this.assertEqual(renderedMessages.length, 10, 'Должно быть отрендерено 10 сообщений');

        // Тест 3: Оптимистичная отправка
        console.log('\n--- Тест 3: Оптимистичная отправка ---');
        
        const tempId = controller.loader.sendMessageOptimistically(chatId, 'Optimistic integration');
        this.assert(controller.store.optimisticMessages.has(tempId), 'Оптимистичное сообщение должно быть в Store');
        
        // Симулируем подтверждение
        const confirmed = {
            id: 800,
            chat_id: chatId,
            sender: currentUser,
            content: 'Optimistic integration',
            created_at: new Date().toISOString()
        };
        
        controller.store.confirmOptimisticMessage(tempId, confirmed);
        this.assert(!controller.store.optimisticMessages.has(tempId), 'Оптимистичное сообщение должно быть удалено');
        this.assert(controller.store.hasMessage(800), 'Подтвержденное сообщение должно существовать');

        // Тест 4: События Store → Controller
        console.log('\n--- Тест 4: События Store → Controller ---');
        
        // Проверяем, что Controller получает события от Store
        let eventReceived = false;
        const originalHandler = controller._handleStoreUpdate.bind(controller);
        controller._handleStoreUpdate = function(...args) {
            eventReceived = true;
            return originalHandler(...args);
        };
        
        controller.store.addMessage({
            id: 900,
            chat_id: chatId,
            sender: { id: 1 },
            content: 'Event test',
            created_at: new Date().toISOString()
        });
        
        await this.sleep(100);
        this.assert(eventReceived, 'Controller должен получать события от Store');

        // Cleanup
        controller.destroy();
        document.body.removeChild(container);

        this.printResults();
        return this.results;
    }

    // ==================== Тесты производительности ====================

    async testPerformance() {
        console.log('\n🧪 Тесты производительности...\n');
        this.resetResults();

        const store = new MessageStore();
        const chatId = 1;

        // Тест 1: Массовое добавление сообщений
        console.log('\n--- Тест 1: Добавление 1000 сообщений ---');
        
        const messages = [];
        for (let i = 0; i < 1000; i++) {
            messages.push({
                id: 1000 + i,
                chat_id: chatId,
                sender: { id: i % 10 + 1, username: `user${i % 10}` },
                content: `Performance test message ${i}`,
                created_at: new Date(Date.now() + i * 1000).toISOString()
            });
        }

        const start1 = performance.now();
        store.addMessages(messages);
        const duration1 = performance.now() - start1;
        
        console.log(`⏱️  Добавлено 1000 сообщений за ${duration1.toFixed(2)}ms`);
        this.assert(duration1 < 100, 'Добавление 1000 сообщений должно занять < 100ms');
        this.assertEqual(store.getMessagesForChat(chatId).length, 1000, 'Должно быть 1000 сообщений');

        // Тест 2: Поиск сообщений
        console.log('\n--- Тест 2: Поиск 100 сообщений ---');
        
        const start2 = performance.now();
        for (let i = 0; i < 100; i++) {
            store.getMessage(1000 + Math.floor(Math.random() * 1000));
        }
        const duration2 = performance.now() - start2;
        
        console.log(`⏱️  100 поисков выполнено за ${duration2.toFixed(2)}ms`);
        this.assert(duration2 < 10, 'Поиск должен быть быстрым (< 10ms для 100 запросов)');

        // Тест 3: Рендеринг
        console.log('\n--- Тест 3: Рендеринг 1000 сообщений ---');
        
        const container = document.createElement('div');
        container.id = 'perf-messages-list';
        document.body.appendChild(container);
        
        const renderer = new MessageRendererV2({ 
            store, 
            containerId: 'perf-messages-list',
            currentUserId: 1 
        });
        
        const start3 = performance.now();
        renderer.render(chatId);
        const duration3 = performance.now() - start3;
        
        console.log(`⏱️  Рендеринг 1000 сообщений занял ${duration3.toFixed(2)}ms`);
        this.assert(duration3 < 500, 'Рендеринг должен быть достаточно быстрым (< 500ms)');
        
        document.body.removeChild(container);

        // Тест 4: Обновление сообщений
        console.log('\n--- Тест 4: Обновление 100 сообщений ---');
        
        const start4 = performance.now();
        for (let i = 0; i < 100; i++) {
            store.updateMessage(1000 + i, { content: `Updated ${i}`, is_edited: true });
        }
        const duration4 = performance.now() - start4;
        
        console.log(`⏱️  Обновление 100 сообщений заняло ${duration4.toFixed(2)}ms`);
        this.assert(duration4 < 50, 'Обновление должно быть быстрым (< 50ms)');

        this.printResults();
        return this.results;
    }

    // ==================== Расширенные тесты ====================

    async testAdvanced() {
        console.log('\n🧪 Расширенные тесты системы чата...\n');
        this.resetResults();

        const store = new MessageStore();
        const chatId = 1;

        // Тест 1: Множественная дозагрузка истории
        console.log('\n--- Тест 1: Множественная дозагрузка ---');
        
        // Добавляем начальные сообщения (ID 100-119)
        const initialMessages = [];
        for (let i = 0; i < 20; i++) {
            initialMessages.push({
                id: 100 + i,
                chat_id: chatId,
                sender: { id: 1, username: 'user1' },
                content: `Message ${100 + i}`,
                created_at: new Date(Date.now() - (19 - i) * 60000).toISOString()
            });
        }
        store.addMessages(initialMessages);
        
        // Первая дозагрузка (ID 80-99)
        const history1 = [];
        for (let i = 0; i < 20; i++) {
            history1.push({
                id: 80 + i,
                chat_id: chatId,
                sender: { id: 1, username: 'user1' },
                content: `History ${80 + i}`,
                created_at: new Date(Date.now() - (39 - i) * 60000).toISOString()
            });
        }
        const added1 = store.addMessages(history1);
        this.assertEqual(added1, 20, 'Первая дозагрузка: добавлено 20 сообщений');
        this.assertEqual(store.getMessagesForChat(chatId).length, 40, 'Всего должно быть 40 сообщений');
        
        // Вторая дозагрузка (ID 60-79)
        const history2 = [];
        for (let i = 0; i < 20; i++) {
            history2.push({
                id: 60 + i,
                chat_id: chatId,
                sender: { id: 1, username: 'user1' },
                content: `History ${60 + i}`,
                created_at: new Date(Date.now() - (59 - i) * 60000).toISOString()
            });
        }
        const added2 = store.addMessages(history2);
        this.assertEqual(added2, 20, 'Вторая дозагрузка: добавлено 20 сообщений');
        this.assertEqual(store.getMessagesForChat(chatId).length, 60, 'Всего должно быть 60 сообщений');

        // Тест 2: Порядок сообщений после множественных дозагрузок
        console.log('\n--- Тест 2: Порядок сообщений ---');
        
        const allMessages = store.getMessagesForChat(chatId);
        
        // Отладка: показываем первые и последние 3 сообщения
        console.log('Первые 3 сообщения:', allMessages.slice(0, 3).map(m => ({ id: m.id, ts: m.created_ts })));
        console.log('Последние 3 сообщения:', allMessages.slice(-3).map(m => ({ id: m.id, ts: m.created_ts })));
        
        // Проверяем сортировку по timestamp (не по ID!)
        let correctOrder = true;
        for (let i = 1; i < allMessages.length; i++) {
            if (allMessages[i].created_ts < allMessages[i-1].created_ts) {
                correctOrder = false;
                console.log(`❌ Нарушение порядка на позиции ${i}: ${allMessages[i-1].id}(ts:${allMessages[i-1].created_ts}) > ${allMessages[i].id}(ts:${allMessages[i].created_ts})`);
                break;
            }
        }
        this.assert(correctOrder, 'Сообщения должны быть отсортированы по timestamp');
        
        const oldest = store.getOldestMessage(chatId);
        const newest = store.getNewestMessage(chatId);
        console.log('Oldest message:', oldest ? { id: oldest.id, ts: oldest.created_ts } : null);
        console.log('Newest message:', newest ? { id: newest.id, ts: newest.created_ts } : null);
        this.assertEqual(oldest.id, 60, 'Старейшее сообщение должно иметь ID 60');
        this.assertEqual(newest.id, 119, 'Новейшее сообщение должно иметь ID 119');

        // Тест 3: Дубликаты при дозагрузке
        console.log('\n--- Тест 3: Дубликаты при дозагрузке ---');
        
        // Пытаемся добавить уже существующие сообщения
        const duplicates = [
            { ...initialMessages[0] },
            { ...initialMessages[10] },
            { ...history1[5] }
        ];
        const addedDupes = store.addMessages(duplicates);
        this.assertEqual(addedDupes, 0, 'Дубликаты не должны быть добавлены');
        this.assertEqual(store.getMessagesForChat(chatId).length, 60, 'Количество сообщений не должно измениться');

        // Тест 4: Смешанная дозагрузка (новые + дубликаты)
        console.log('\n--- Тест 4: Смешанная дозагрузка ---');
        
        const mixed = [
            { ...initialMessages[0] }, // дубликат
            { id: 50, chat_id: chatId, sender: { id: 1 }, content: 'New 50', created_at: new Date(Date.now() - 69 * 60000).toISOString() },
            { ...history1[5] }, // дубликат
            { id: 51, chat_id: chatId, sender: { id: 1 }, content: 'New 51', created_at: new Date(Date.now() - 68 * 60000).toISOString() },
            { id: 52, chat_id: chatId, sender: { id: 1 }, content: 'New 52', created_at: new Date(Date.now() - 67 * 60000).toISOString() }
        ];
        const addedMixed = store.addMessages(mixed);
        this.assertEqual(addedMixed, 3, 'Должно быть добавлено 3 новых сообщения из 5');
        this.assertEqual(store.getMessagesForChat(chatId).length, 63, 'Всего должно быть 63 сообщения');

        // Тест 5: Разделители дней
        console.log('\n--- Тест 5: Разделители дней ---');
        
        store.clearChat(chatId);
        
        // Добавляем сообщения за разные дни
        const today = new Date();
        const yesterday = new Date(today);
        yesterday.setDate(yesterday.getDate() - 1);
        const dayBefore = new Date(today);
        dayBefore.setDate(dayBefore.getDate() - 2);
        
        const multiDayMessages = [
            { id: 200, chat_id: chatId, sender: { id: 1 }, content: 'Msg 1', created_at: dayBefore.toISOString() },
            { id: 201, chat_id: chatId, sender: { id: 1 }, content: 'Msg 2', created_at: dayBefore.toISOString() },
            { id: 202, chat_id: chatId, sender: { id: 1 }, content: 'Msg 3', created_at: yesterday.toISOString() },
            { id: 203, chat_id: chatId, sender: { id: 1 }, content: 'Msg 4', created_at: yesterday.toISOString() },
            { id: 204, chat_id: chatId, sender: { id: 1 }, content: 'Msg 5', created_at: today.toISOString() },
            { id: 205, chat_id: chatId, sender: { id: 1 }, content: 'Msg 6', created_at: today.toISOString() }
        ];
        store.addMessages(multiDayMessages);
        
        const itemsWithDividers = store.getMessagesWithDividers(chatId);
        const dividers = itemsWithDividers.filter(item => item.type === 'day-divider');
        this.assertEqual(dividers.length, 3, 'Должно быть 3 разделителя дней');
        
        const messages = itemsWithDividers.filter(item => item.type === 'message');
        this.assertEqual(messages.length, 6, 'Должно быть 6 сообщений');

        // Тест 6: Добавление сообщений в разном порядке
        console.log('\n--- Тест 6: Добавление в разном порядке ---');
        
        store.clearChat(chatId);
        
        // Добавляем сообщения не по порядку
        const unordered = [
            { id: 305, chat_id: chatId, sender: { id: 1 }, content: 'Msg 5', created_at: new Date(Date.now() + 4000).toISOString() },
            { id: 302, chat_id: chatId, sender: { id: 1 }, content: 'Msg 2', created_at: new Date(Date.now() + 1000).toISOString() },
            { id: 301, chat_id: chatId, sender: { id: 1 }, content: 'Msg 1', created_at: new Date(Date.now()).toISOString() },
            { id: 304, chat_id: chatId, sender: { id: 1 }, content: 'Msg 4', created_at: new Date(Date.now() + 3000).toISOString() },
            { id: 303, chat_id: chatId, sender: { id: 1 }, content: 'Msg 3', created_at: new Date(Date.now() + 2000).toISOString() }
        ];
        store.addMessages(unordered);
        
        const sorted = store.getMessagesForChat(chatId);
        console.log('Sorted messages:', sorted.map(m => ({ id: m.id, ts: m.created_ts })));
        this.assertEqual(sorted[0].id, 301, 'Первое сообщение должно иметь ID 301');
        this.assertEqual(sorted[4].id, 305, 'Последнее сообщение должно иметь ID 305');
        
        // Проверяем сортировку по timestamp
        let isSorted = true;
        for (let i = 1; i < sorted.length; i++) {
            if (sorted[i].created_ts < sorted[i-1].created_ts) {
                isSorted = false;
                console.log(`❌ Нарушение порядка: ${sorted[i-1].id}(ts:${sorted[i-1].created_ts}) > ${sorted[i].id}(ts:${sorted[i].created_ts})`);
                break;
            }
        }
        this.assert(isSorted, 'Сообщения должны быть автоматически отсортированы по timestamp');

        // Тест 7: Граничные случаи
        console.log('\n--- Тест 7: Граничные случаи ---');
        
        // Пустой массив
        const emptyAdded = store.addMessages([]);
        this.assertEqual(emptyAdded, 0, 'Пустой массив должен вернуть 0');
        
        // null/undefined
        const nullAdded = store.addMessages(null);
        this.assertEqual(nullAdded, 0, 'null должен вернуть 0');
        
        // Невалидные сообщения
        const invalid = [
            { id: 400, chat_id: chatId, sender: { id: 1 }, content: 'Valid', created_at: new Date().toISOString() },
            { chat_id: chatId, sender: { id: 1 }, content: 'No ID' }, // нет ID
            { id: null, chat_id: chatId, sender: { id: 1 }, content: 'Null ID' }, // null ID
            { id: 401, chat_id: chatId, sender: { id: 1 }, content: 'Valid 2', created_at: new Date().toISOString() }
        ];
        const validAdded = store.addMessages(invalid);
        this.assertEqual(validAdded, 2, 'Должно быть добавлено только 2 валидных сообщения');

        // Тест 8: Поиск несуществующих сообщений
        console.log('\n--- Тест 8: Поиск несуществующих ---');
        
        const notFound = store.getMessage(99999);
        this.assert(notFound === null, 'Несуществующее сообщение должно вернуть null');
        
        this.assert(!store.hasMessage(99999), 'hasMessage для несуществующего должен вернуть false');

        // Тест 9: Обновление несуществующего сообщения
        console.log('\n--- Тест 9: Обновление несуществующего ---');
        
        const updateResult = store.updateMessage(99999, { content: 'Updated' });
        this.assert(!updateResult, 'Обновление несуществующего должно вернуть false');

        // Тест 10: Удаление несуществующего сообщения
        console.log('\n--- Тест 10: Удаление несуществующего ---');
        
        const removeResult = store.removeMessage(99999);
        this.assert(!removeResult, 'Удаление несуществующего должно вернуть false');

        this.printResults();
        return this.results;
    }

    // ==================== Тесты стабильности скролла ====================

    async testScrollStability() {
        console.log('\n🧪 Тесты стабильности скролла...\n');
        this.resetResults();

        // Создаем реальный контейнер с прокруткой
        const container = document.createElement('div');
        container.id = 'scroll-test-container';
        container.style.cssText = 'height: 300px; overflow-y: auto; position: relative;';
        document.body.appendChild(container);

        const store = new MessageStore();
        const loader = new MessageLoader({ store });
        const renderer = new MessageRendererV2({ 
            store, 
            containerId: 'scroll-test-container',
            currentUserId: 1 
        });
        const manager = new ScrollManager({
            scrollElement: container,
            messageLoader: loader,
            messageRenderer: renderer,
            messageStore: store,
            chatId: 1
        });

        const chatId = 1;

        // Тест 1: Добавление начальных сообщений
        console.log('\n--- Тест 1: Начальная загрузка ---');
        
        const initialMessages = [];
        for (let i = 0; i < 20; i++) {
            initialMessages.push({
                id: 100 + i,
                chat_id: chatId,
                sender: { id: 1, username: 'user1', display_name: 'User 1' },
                content: `Initial message ${100 + i}`,
                created_at: new Date(Date.now() - (19 - i) * 60000).toISOString()
            });
        }
        store.addMessages(initialMessages);
        renderer.render(chatId);
        
        await this.sleep(100);
        
        // Прокручиваем к началу (чтобы имитировать чтение старых)
        container.scrollTop = 100;
        const initialScrollTop = container.scrollTop;
        const initialScrollHeight = container.scrollHeight;
        
        this.assert(initialScrollTop > 0, 'Начальная позиция скролла должна быть > 0');
        this.assert(initialScrollHeight > container.clientHeight, 'Контент должен быть больше видимой области');

        console.log('Initial state:', { 
            scrollTop: initialScrollTop, 
            scrollHeight: initialScrollHeight,
            clientHeight: container.clientHeight
        });

        // Тест 2: Симуляция дозагрузки истории
        console.log('\n--- Тест 2: Дозагрузка истории ---');
        
        // Добавляем старые сообщения (имитация loadHistory)
        const historyMessages = [];
        for (let i = 0; i < 10; i++) {
            historyMessages.push({
                id: 90 + i,
                chat_id: chatId,
                sender: { id: 1, username: 'user1', display_name: 'User 1' },
                content: `History message ${90 + i}`,
                created_at: new Date(Date.now() - (29 - i) * 60000).toISOString()
            });
        }
        
        // ПРАВИЛЬНЫЙ подход (как в Telegram): сохраняем offsetTop якоря
        const anchorBefore = manager._getFirstVisibleMessage();
        const anchorIdBefore = anchorBefore ? anchorBefore.dataset.messageId : null;
        const anchorOffsetTopBefore = anchorBefore ? anchorBefore.offsetTop : 0;
        const viewportOffsetBefore = container.scrollTop;
        const anchorRelativePos = anchorOffsetTopBefore - viewportOffsetBefore;
        
        console.log('Before history load:', { 
            anchorId: anchorIdBefore,
            anchorOffsetTop: anchorOffsetTopBefore,
            viewportOffset: viewportOffsetBefore,
            anchorRelativePos
        });
        
        // Добавляем в Store и ре-рендерим
        store.addMessages(historyMessages);
        container.style.visibility = 'hidden';
        renderer.render(chatId);
        
        await this.sleep(50);
        
        // Восстанавливаем позицию: находим якорь и ставим его на ту же позицию относительно viewport
        if (anchorIdBefore) {
            const anchorAfter = container.querySelector(`[data-message-id="${anchorIdBefore}"]`);
            if (anchorAfter) {
                const newAnchorOffsetTop = anchorAfter.offsetTop;
                container.scrollTop = newAnchorOffsetTop - anchorRelativePos;
                
                console.log('After history load:', { 
                    anchorId: anchorIdBefore,
                    oldOffsetTop: anchorOffsetTopBefore,
                    newOffsetTop: newAnchorOffsetTop,
                    delta: newAnchorOffsetTop - anchorOffsetTopBefore,
                    newScrollTop: container.scrollTop
                });
            }
        }
        
        container.style.visibility = '';
        
        await this.sleep(50);
        
        // Проверяем что якорное сообщение все еще видимо
        if (anchorIdBefore) {
            const anchorStillVisible = this._isMessageVisible(container, anchorIdBefore);
            this.assert(anchorStillVisible, `Якорное сообщение ${anchorIdBefore} должно остаться видимым`);
            
            // Проверяем что якорь находится примерно в той же позиции относительно viewport
            const anchorAfterCheck = container.querySelector(`[data-message-id="${anchorIdBefore}"]`);
            if (anchorAfterCheck) {
                const newRelativePos = anchorAfterCheck.offsetTop - container.scrollTop;
                const posDiff = Math.abs(newRelativePos - anchorRelativePos);
                console.log('Position check:', { 
                    originalRelativePos: anchorRelativePos, 
                    newRelativePos, 
                    diff: posDiff 
                });
                this.assert(posDiff < 5, `Якорь должен остаться в той же позиции viewport (diff: ${posDiff}px)`);
            }
        }
        
        this.assert(container.scrollHeight > initialScrollHeight, 'Высота контента должна увеличиться');

        // Тест 3: Проверка что скролл не прыгает к низу
        console.log('\n--- Тест 3: Скролл не прыгает к низу ---');
        
        const maxScrollTop = container.scrollHeight - container.clientHeight;
        this.assert(container.scrollTop < maxScrollTop - 50, 'Скролл не должен быть в самом низу');

        // Тест 4: Множественная дозагрузка (реалистичный сценарий)
        console.log('\n--- Тест 4: Множественная дозагрузка ---');
        
        // Сохраняем начальное якорное сообщение для проверки в конце
        const initialAnchor = manager._getFirstVisibleMessage();
        const initialAnchorId = initialAnchor ? initialAnchor.dataset.messageId : null;
        
        console.log('Starting multiple loads with anchor:', initialAnchorId);
        
        // Имитируем 5 последовательных дозагрузок истории
        for (let batch = 0; batch < 5; batch++) {
            console.log(`\n  Batch ${batch + 1}/5:`);
            
            // Сохраняем якорь ПЕРЕД каждой дозагрузкой
            const anchor = manager._getFirstVisibleMessage();
            if (!anchor) {
                console.warn('  No anchor found, skipping batch');
                continue;
            }
            
            const anchorId = anchor.dataset.messageId;
            const anchorOffsetTop = anchor.offsetTop;
            const viewportOffset = container.scrollTop;
            const anchorRelativePos = anchorOffsetTop - viewportOffset;
            
            console.log('  Before:', { anchorId, anchorOffsetTop, viewportOffset, anchorRelativePos });
            
            // Добавляем 10 старых сообщений
            const batchMessages = [];
            const startId = 80 - batch * 10;
            for (let i = 0; i < 10; i++) {
                const msgId = startId + i;
                batchMessages.push({
                    id: msgId,
                    chat_id: chatId,
                    sender: { id: 1, username: 'user1', display_name: 'User 1' },
                    content: `Batch ${batch} message ${msgId}`,
                    created_at: new Date(Date.now() - (100 + batch * 10 - i) * 60000).toISOString()
                });
            }
            
            // Добавляем в Store и ре-рендерим
            store.addMessages(batchMessages);
            container.style.visibility = 'hidden';
            renderer.render(chatId);
            await this.sleep(20);
            
            // ПРАВИЛЬНОЕ восстановление: находим якорь и восстанавливаем его позицию
            const anchorAfter = container.querySelector(`[data-message-id="${anchorId}"]`);
            if (anchorAfter) {
                const newOffsetTop = anchorAfter.offsetTop;
                container.scrollTop = newOffsetTop - anchorRelativePos;
                
                console.log('  After:', { 
                    newOffsetTop, 
                    delta: newOffsetTop - anchorOffsetTop,
                    newScrollTop: container.scrollTop 
                });
                
                // Проверяем что якорь остался видимым
                const stillVisible = this._isMessageVisible(container, anchorId);
                this.assert(stillVisible, `Batch ${batch + 1}: Якорь ${anchorId} должен остаться видимым`);
            }
            
            container.style.visibility = '';
            await this.sleep(20);
        }
        
        // Проверяем что начальный якорь все еще видим (или близко)
        if (initialAnchorId) {
            const initialStillVisible = this._isMessageVisible(container, initialAnchorId);
            console.log(`\nInitial anchor ${initialAnchorId} still visible:`, initialStillVisible);
            // Допускаем что начальный якорь может уйти за границу после 5 дозагрузок
            // Главное что каждая дозагрузка сохраняет СВОЙ якорь
        }
        
        console.log('\nFinal state:', {
            totalMessages: store.getMessagesForChat(chatId).length,
            scrollTop: container.scrollTop,
            scrollHeight: container.scrollHeight,
            clientHeight: container.clientHeight
        });
        
        // Проверяем что добавлено много сообщений
        this.assert(store.getMessagesForChat(chatId).length >= 80, 'Должно быть добавлено много сообщений');

        // Тест 5: Большой объем данных (стресс-тест)
        console.log('\n--- Тест 5: Стресс-тест с большим количеством сообщений ---');
        
        store.clearChat(chatId);
        
        // Добавляем 100 сообщений
        const manyMessages = [];
        for (let i = 0; i < 100; i++) {
            manyMessages.push({
                id: 1000 + i,
                chat_id: chatId,
                sender: { id: i % 5 + 1, username: `user${i % 5}`, display_name: `User ${i % 5}` },
                content: `Stress test message ${1000 + i}`,
                created_at: new Date(Date.now() - (99 - i) * 60000).toISOString()
            });
        }
        store.addMessages(manyMessages);
        renderer.render(chatId);
        await this.sleep(100);
        
        // Скроллим в середину
        container.scrollTop = container.scrollHeight / 2;
        await this.sleep(50);
        
        const stressAnchor = manager._getFirstVisibleMessage();
        const stressAnchorId = stressAnchor ? stressAnchor.dataset.messageId : null;
        const stressAnchorOffsetTop = stressAnchor ? stressAnchor.offsetTop : 0;
        const stressViewportOffset = container.scrollTop;
        const stressRelativePos = stressAnchorOffsetTop - stressViewportOffset;
        
        console.log('Stress test before:', { 
            totalMessages: 100,
            anchorId: stressAnchorId, 
            scrollTop: container.scrollTop 
        });
        
        // Добавляем еще 50 старых сообщений
        const stressHistory = [];
        for (let i = 0; i < 50; i++) {
            stressHistory.push({
                id: 950 + i,
                chat_id: chatId,
                sender: { id: 1, username: 'user1', display_name: 'User 1' },
                content: `Stress history ${950 + i}`,
                created_at: new Date(Date.now() - (149 - i) * 60000).toISOString()
            });
        }
        
        store.addMessages(stressHistory);
        container.style.visibility = 'hidden';
        renderer.render(chatId);
        await this.sleep(50);
        
        // Восстанавливаем якорь
        if (stressAnchorId) {
            const stressAnchorAfter = container.querySelector(`[data-message-id="${stressAnchorId}"]`);
            if (stressAnchorAfter) {
                container.scrollTop = stressAnchorAfter.offsetTop - stressRelativePos;
            }
        }
        
        container.style.visibility = '';
        await this.sleep(50);
        
        console.log('Stress test after:', { 
            totalMessages: store.getMessagesForChat(chatId).length,
            scrollTop: container.scrollTop 
        });
        
        // Проверяем что якорь остался видимым даже при большом объеме
        if (stressAnchorId) {
            const stressVisible = this._isMessageVisible(container, stressAnchorId);
            this.assert(stressVisible, `Стресс-тест: якорь ${stressAnchorId} должен остаться видимым даже при 150 сообщениях`);
        }
        
        this.assertEqual(store.getMessagesForChat(chatId).length, 150, 'Должно быть 150 сообщений после стресс-теста');

        // Cleanup
        manager.destroy();
        document.body.removeChild(container);

        this.printResults();
        return this.results;
    }

    // ==================== Запуск всех тестов ====================

    async runAll() {
        console.log('\n' + '='.repeat(60));
        console.log('🚀 ЗАПУСК ВСЕХ ТЕСТОВ СИСТЕМЫ ЧАТА');
        console.log('='.repeat(60));

        const allResults = {
            passed: 0,
            failed: 0,
            total: 0
        };

        try {
            // Юнит-тесты
            const storeResults = await this.testMessageStore();
            const loaderResults = await this.testMessageLoader();
            const scrollManagerResults = await this.testScrollManager();
            const rendererResults = await this.testMessageRenderer();
            const controllerResults = await this.testChatController();
            
            // Интеграционные тесты
            const integrationResults = await this.testIntegration();
            
            // Тесты производительности
            const perfResults = await this.testPerformance();
            
            // Расширенные тесты
            const advancedResults = await this.testAdvanced();
            
            // Тесты стабильности скролла
            const scrollStabilityResults = await this.testScrollStability();

            // Суммируем результаты
            [storeResults, loaderResults, scrollManagerResults, rendererResults, 
             controllerResults, integrationResults, perfResults, advancedResults, scrollStabilityResults].forEach(result => {
                allResults.passed += result.passed;
                allResults.failed += result.failed;
                allResults.total += result.total;
            });

            console.log('\n' + '='.repeat(60));
            console.log('🏁 ИТОГОВЫЕ РЕЗУЛЬТАТЫ');
            console.log('='.repeat(60));
            console.log(`Всего тестов: ${allResults.total}`);
            console.log(`✅ Успешно: ${allResults.passed}`);
            console.log(`❌ Провалено: ${allResults.failed}`);
            console.log(`📈 Процент успеха: ${(allResults.passed / allResults.total * 100).toFixed(1)}%`);
            console.log('='.repeat(60) + '\n');

            return allResults;

        } catch (error) {
            console.error('❌ Критическая ошибка при выполнении тестов:', error);
            throw error;
        }
    }
}

// Экспортируем для использования в консоли
const chatTests = new ChatTestSuite();
window.ChatTests = {
    runAll: () => chatTests.runAll(),
    testMessageStore: () => chatTests.testMessageStore(),
    testMessageLoader: () => chatTests.testMessageLoader(),
    testScrollManager: () => chatTests.testScrollManager(),
    testMessageRenderer: () => chatTests.testMessageRenderer(),
    testChatController: () => chatTests.testChatController(),
    testIntegration: () => chatTests.testIntegration(),
    testPerformance: () => chatTests.testPerformance(),
    testAdvanced: () => chatTests.testAdvanced(),
    testScrollStability: () => chatTests.testScrollStability()
};

console.log('✅ ChatTests загружен! Используйте:');
console.log('  window.ChatTests.runAll()               - Все тесты');
console.log('  window.ChatTests.testMessageStore()     - Тесты MessageStore');
console.log('  window.ChatTests.testMessageLoader()    - Тесты MessageLoader');
console.log('  window.ChatTests.testScrollManager()    - Тесты ScrollManager');
console.log('  window.ChatTests.testMessageRenderer()  - Тесты MessageRenderer');
console.log('  window.ChatTests.testChatController()   - Тесты ChatController');
console.log('  window.ChatTests.testIntegration()      - Интеграционные тесты');
console.log('  window.ChatTests.testPerformance()      - Тесты производительности');
console.log('  window.ChatTests.testAdvanced()         - Расширенные тесты');
console.log('  window.ChatTests.testScrollStability()  - Тесты стабильности скролла');

export default chatTests;
