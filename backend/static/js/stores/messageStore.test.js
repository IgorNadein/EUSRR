/**
 * @fileoverview Тесты для MessageStore
 * Простые тесты для проверки основной функциональности Store
 */

import { MessageStore } from '../stores/messageStore.js';

/**
 * Вспомогательная функция для создания тестового сообщения
 */
function createTestMessage(id, chatId, content, timestamp = Date.now()) {
    return {
        id,
        chat_id: chatId,
        author_id: 1,
        content,
        created_ts: timestamp,
        is_edited: false,
        reactions_summary: {}
    };
}

/**
 * Простой тест-раннер
 */
function runTests() {
    console.log('🧪 Running MessageStore tests...\n');
    
    let passed = 0;
    let failed = 0;

    // Test 1: Создание Store
    try {
        const store = new MessageStore({ currentUserId: 1 });
        console.assert(store.messages.size === 0, 'Store should start empty');
        console.log('✅ Test 1: Store creation - PASSED');
        passed++;
    } catch (error) {
        console.error('❌ Test 1: Store creation - FAILED:', error);
        failed++;
    }

    // Test 2: Добавление сообщения
    try {
        const store = new MessageStore({ currentUserId: 1 });
        const msg = createTestMessage(1, 100, 'Test message');
        const added = store.addMessage(msg);
        
        console.assert(added === true, 'addMessage should return true');
        console.assert(store.messages.size === 1, 'Store should have 1 message');
        console.assert(store.getMessage(1) !== null, 'getMessage should return the message');
        console.log('✅ Test 2: Add message - PASSED');
        passed++;
    } catch (error) {
        console.error('❌ Test 2: Add message - FAILED:', error);
        failed++;
    }

    // Test 3: Предотвращение дубликатов
    try {
        const store = new MessageStore({ currentUserId: 1 });
        const msg = createTestMessage(1, 100, 'Test message');
        
        store.addMessage(msg);
        const duplicate = store.addMessage(msg);
        
        console.assert(duplicate === false, 'Adding duplicate should return false');
        console.assert(store.messages.size === 1, 'Store should still have 1 message');
        console.log('✅ Test 3: Duplicate prevention - PASSED');
        passed++;
    } catch (error) {
        console.error('❌ Test 3: Duplicate prevention - FAILED:', error);
        failed++;
    }

    // Test 4: Batch добавление
    try {
        const store = new MessageStore({ currentUserId: 1 });
        const messages = [
            createTestMessage(1, 100, 'Message 1', 1000),
            createTestMessage(2, 100, 'Message 2', 2000),
            createTestMessage(3, 100, 'Message 3', 3000)
        ];
        
        const count = store.addMessages(messages);
        
        console.assert(count === 3, 'addMessages should return count of 3');
        console.assert(store.messages.size === 3, 'Store should have 3 messages');
        console.log('✅ Test 4: Batch add - PASSED');
        passed++;
    } catch (error) {
        console.error('❌ Test 4: Batch add - FAILED:', error);
        failed++;
    }

    // Test 5: Обновление сообщения
    try {
        const store = new MessageStore({ currentUserId: 1 });
        const msg = createTestMessage(1, 100, 'Original');
        
        store.addMessage(msg);
        const updated = store.updateMessage(1, { content: 'Updated', is_edited: true });
        
        console.assert(updated === true, 'updateMessage should return true');
        
        const retrieved = store.getMessage(1);
        console.assert(retrieved.content === 'Updated', 'Content should be updated');
        console.assert(retrieved.is_edited === true, 'is_edited should be true');
        console.log('✅ Test 5: Update message - PASSED');
        passed++;
    } catch (error) {
        console.error('❌ Test 5: Update message - FAILED:', error);
        failed++;
    }

    // Test 6: Удаление сообщения
    try {
        const store = new MessageStore({ currentUserId: 1 });
        const msg = createTestMessage(1, 100, 'To be deleted');
        
        store.addMessage(msg);
        const removed = store.removeMessage(1);
        
        console.assert(removed === true, 'removeMessage should return true');
        console.assert(store.messages.size === 0, 'Store should be empty');
        console.assert(store.getMessage(1) === null, 'getMessage should return null');
        console.log('✅ Test 6: Remove message - PASSED');
        passed++;
    } catch (error) {
        console.error('❌ Test 6: Remove message - FAILED:', error);
        failed++;
    }

    // Test 7: Получение сообщений чата
    try {
        const store = new MessageStore({ currentUserId: 1 });
        const messages = [
            createTestMessage(1, 100, 'Chat 100 msg 1'),
            createTestMessage(2, 100, 'Chat 100 msg 2'),
            createTestMessage(3, 200, 'Chat 200 msg 1')
        ];
        
        store.addMessages(messages);
        
        const chat100 = store.getMessagesForChat(100);
        const chat200 = store.getMessagesForChat(200);
        
        console.assert(chat100.length === 2, 'Chat 100 should have 2 messages');
        console.assert(chat200.length === 1, 'Chat 200 should have 1 message');
        console.log('✅ Test 7: Get messages for chat - PASSED');
        passed++;
    } catch (error) {
        console.error('❌ Test 7: Get messages for chat - FAILED:', error);
        failed++;
    }

    // Test 8: Сортировка по timestamp
    try {
        const store = new MessageStore({ currentUserId: 1 });
        const messages = [
            createTestMessage(3, 100, 'Third', 3000),
            createTestMessage(1, 100, 'First', 1000),
            createTestMessage(2, 100, 'Second', 2000)
        ];
        
        store.addMessages(messages);
        const chat = store.getMessagesForChat(100);
        
        console.assert(chat[0].id === 1, 'First message should have id 1');
        console.assert(chat[1].id === 2, 'Second message should have id 2');
        console.assert(chat[2].id === 3, 'Third message should have id 3');
        console.log('✅ Test 8: Message sorting - PASSED');
        passed++;
    } catch (error) {
        console.error('❌ Test 8: Message sorting - FAILED:', error);
        failed++;
    }

    // Test 9: Day-dividers
    try {
        const store = new MessageStore({ currentUserId: 1 });
        const today = new Date();
        const yesterday = new Date(today);
        yesterday.setDate(yesterday.getDate() - 1);
        
        const messages = [
            createTestMessage(1, 100, 'Yesterday msg', yesterday.getTime()),
            createTestMessage(2, 100, 'Today msg 1', today.getTime()),
            createTestMessage(3, 100, 'Today msg 2', today.getTime() + 1000)
        ];
        
        store.addMessages(messages);
        const items = store.getMessagesWithDividers(100);
        
        // Должно быть: divider "Вчера" + msg1 + divider "Сегодня" + msg2 + msg3
        console.assert(items.length === 5, 'Should have 5 items (2 dividers + 3 messages)');
        console.assert(items[0].type === 'divider', 'First should be divider');
        console.assert(items[1].type === 'message', 'Second should be message');
        console.assert(items[2].type === 'divider', 'Third should be divider');
        console.log('✅ Test 9: Day-dividers - PASSED');
        passed++;
    } catch (error) {
        console.error('❌ Test 9: Day-dividers - FAILED:', error);
        failed++;
    }

    // Test 10: Подписки (subscribe/unsubscribe)
    try {
        const store = new MessageStore({ currentUserId: 1 });
        let eventReceived = null;
        
        const unsubscribe = store.subscribe((event, data) => {
            eventReceived = event;
        });
        
        store.addMessage(createTestMessage(1, 100, 'Test'));
        
        console.assert(eventReceived === 'message_added', 'Should receive message_added event');
        
        eventReceived = null;
        unsubscribe();
        
        store.addMessage(createTestMessage(2, 100, 'Test 2'));
        console.assert(eventReceived === null, 'Should not receive event after unsubscribe');
        
        console.log('✅ Test 10: Subscriptions - PASSED');
        passed++;
    } catch (error) {
        console.error('❌ Test 10: Subscriptions - FAILED:', error);
        failed++;
    }

    // Test 11: Оптимистичные сообщения
    try {
        const store = new MessageStore({ currentUserId: 1 });
        const tempId = 'temp_123';
        const optimisticMsg = {
            ...createTestMessage('temp_123', 100, 'Sending...'),
            temp_id: tempId,
            status: 'sending'
        };
        
        store.addMessage(optimisticMsg, true);
        console.assert(store.optimisticMessages.has(tempId), 'Should have optimistic message');
        
        const serverMsg = createTestMessage(1, 100, 'Sending...');
        serverMsg.temp_id = tempId;
        
        store.confirmOptimisticMessage(tempId, serverMsg);
        
        console.assert(!store.optimisticMessages.has(tempId), 'Should remove optimistic message');
        console.assert(store.getMessage(1) !== null, 'Should have confirmed message');
        console.assert(store.getMessage('temp_123') === null, 'Should remove temp message');
        
        console.log('✅ Test 11: Optimistic messages - PASSED');
        passed++;
    } catch (error) {
        console.error('❌ Test 11: Optimistic messages - FAILED:', error);
        failed++;
    }

    // Test 12: getOldestMessage / getNewestMessage
    try {
        const store = new MessageStore({ currentUserId: 1 });
        const messages = [
            createTestMessage(1, 100, 'First', 1000),
            createTestMessage(2, 100, 'Second', 2000),
            createTestMessage(3, 100, 'Third', 3000)
        ];
        
        store.addMessages(messages);
        
        const oldest = store.getOldestMessage(100);
        const newest = store.getNewestMessage(100);
        
        console.assert(oldest.id === 1, 'Oldest should be message 1');
        console.assert(newest.id === 3, 'Newest should be message 3');
        
        console.log('✅ Test 12: Oldest/Newest message - PASSED');
        passed++;
    } catch (error) {
        console.error('❌ Test 12: Oldest/Newest message - FAILED:', error);
        failed++;
    }

    // Итоги
    console.log('\n' + '='.repeat(50));
    console.log(`✅ Passed: ${passed}`);
    console.log(`❌ Failed: ${failed}`);
    console.log(`📊 Total: ${passed + failed}`);
    console.log('='.repeat(50));
    
    return { passed, failed };
}

// Экспортируем для использования
export { runTests, createTestMessage };

// Автозапуск если файл загружен напрямую
if (typeof window !== 'undefined') {
    window.runMessageStoreTests = runTests;
    console.log('💡 Тесты загружены! Запустите: runMessageStoreTests()');
}
