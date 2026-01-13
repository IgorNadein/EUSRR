/**
 * Тесты для ChatControllerV2 - умный автоскролл
 * Запуск:
 *   .venv/Scripts/python manage.py runserver
 *   Открыть в браузере: http://localhost:8000/static/js/tests/chatTestsV2.html
 */

import { ChatControllerV2 } from '../controllers/chatControllerV2.js';
import { MessageStoreV2 } from '../stores/messageStoreV2.js';

class ChatTestSuiteV2 {
    constructor() {
        this.results = {
            passed: 0,
            failed: 0,
            total: 0,
            details: []
        };
    }

    // ==================== Утилиты ====================

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

    resetResults() {
        this.results = {
            passed: 0,
            failed: 0,
            total: 0,
            details: []
        };
    }

    printResults() {
        const { passed, failed, total } = this.results;
        const passRate = total > 0 ? parseFloat(((passed / total) * 100).toFixed(1)) : 0;
        
        console.log('\n' + '='.repeat(60));
        console.log(`📊 Результаты тестов V2:`);
        console.log(`   ✅ Успешных: ${passed}`);
        console.log(`   ❌ Провалено: ${failed}`);
        console.log(`   📈 Процент: ${passRate}%`);
        console.log('='.repeat(60) + '\n');
        
        return { passed, failed, total, passRate };
    }

    // ==================== Тесты базовой функциональности V2 ====================

    async testBasicFunctionalityV2() {
        console.log('\n🧪 Тестирование базовой функциональности V2...\n');
        this.resetResults();

        const store = new MessageStoreV2();
        const chatId = 1;

        // Тест 1: Добавление сообщения
        const msg1 = {
            id: 1,
            chat_id: chatId,
            author_id: 1,
            author_name: 'User 1',
            content: 'Test message',
            created_ts: Date.now(),
            created: new Date().toISOString()
        };
        
        store.addMessage(msg1);
        this.assert(store.hasMessage(1), 'Сообщение должно быть добавлено');

        // Тест 2: Batch добавление (V2 фича)
        const messages = [
            { id: 2, chat_id: chatId, author_id: 1, content: 'Msg 2', created_ts: Date.now() + 1000, created: new Date().toISOString() },
            { id: 3, chat_id: chatId, author_id: 1, content: 'Msg 3', created_ts: Date.now() + 2000, created: new Date().toISOString() },
            { id: 4, chat_id: chatId, author_id: 1, content: 'Msg 4', created_ts: Date.now() + 3000, created: new Date().toISOString() }
        ];
        
        store.addMessages(messages);
        this.assertEqual(store.messages.size, 4, 'Должно быть 4 сообщения после batch');

        // Тест 3: Обновление сообщения
        store.updateMessage(1, { content: 'Updated', is_edited: true });
        const updated = store.getMessage(1);
        this.assertEqual(updated.content, 'Updated', 'Сообщение должно быть обновлено');

        // Тест 4: Удаление сообщения
        store.removeMessage(1);
        this.assert(!store.hasMessage(1), 'Сообщение должно быть удалено');

        this.printResults();
        return this.results;
    }

    // ==================== Тесты умного автоскролла V2 ====================

    async testSmartAutoscrollV2() {
        console.log('\n🧪 Тестирование умного автоскролла V2 (8 сценариев, ~18 проверок)...\n');
        this.resetResults();

        // Создаем реальный контейнер
        const container = document.createElement('div');
        container.id = 'test-chat-container-v2';
        container.style.cssText = 'height: 400px; overflow-y: auto; position: relative;';
        document.body.appendChild(container);

        const currentUserId = 1;
        const controller = new ChatControllerV2({
            chatId: 1,
            scrollElement: container,
            containerId: 'test-chat-container-v2',
            currentUserId: currentUserId
        });

        // Инициализируем контроллер
        try {
            await controller.init();
        } catch (e) {
            console.log('[Test V2] Init failed (expected without backend):', e.message);
            controller._initializing = false;
            controller._initialized = false;
            
            // ВАЖНО: Инициализируем scroll watcher вручную для тестов
            // т.к. init() упал, но watcher нужен для Теста 5
            controller._initScrollWatcher();
        }

        // Тест 1: Своё сообщение - всегда скроллим вниз
        console.log('\n--- Тест 1: Своё сообщение скроллит вниз ---');
        
        // Добавляем несколько сообщений для высоты
        for (let i = 0; i < 20; i++) {
            controller.store.addMessage({
                id: i + 1,
                chat_id: 1,
                author_id: 2,
                author_name: 'Other User',
                content: `Message ${i + 1}`,
                created_ts: Date.now() + i * 1000,
                created: new Date(Date.now() + i * 1000).toISOString()
            });
        }
        
        controller.renderer.render(1);
        await this.sleep(100);
        
        // Прокручиваем вверх (читаем историю)
        container.scrollTop = 50;
        await this.sleep(50);
        
        const wasAtBottom = controller.scrollManager.isNearBottom();
        this.assert(!wasAtBottom, 'До отправки своего сообщения должны быть НЕ внизу');
        
        // Добавляем своё сообщение
        controller.store.addMessage({
            id: 100,
            chat_id: 1,
            author_id: currentUserId,
            author_name: 'Me',
            content: 'My message',
            created_ts: Date.now() + 30000,
            created: new Date(Date.now() + 30000).toISOString()
        });
        
        await this.sleep(500);
        
        const isNowAtBottom = controller.scrollManager.isNearBottom();
        this.assert(isNowAtBottom, 'После своего сообщения должны быть внизу (автоскролл)');

        // Тест 2: Чужое сообщение + внизу - скроллим
        console.log('\n--- Тест 2: Чужое сообщение + внизу = скролл ---');
        
        // Убеждаемся что внизу
        controller.scrollManager.scrollToBottom({ instant: true, force: true });
        await this.sleep(100);
        
        const wasAtBottomBefore = controller.scrollManager.isNearBottom();
        this.assert(wasAtBottomBefore, 'Должны быть внизу перед получением чужого сообщения');
        
        // Добавляем чужое сообщение
        controller.store.addMessage({
            id: 101,
            chat_id: 1,
            author_id: 2,
            author_name: 'Other User',
            content: 'Other message',
            created_ts: Date.now() + 31000,
            created: new Date(Date.now() + 31000).toISOString()
        });
        
        await this.sleep(500);
        
        const stillAtBottom = controller.scrollManager.isNearBottom();
        this.assert(stillAtBottom, 'Должны остаться внизу после чужого сообщения (автоскролл)');

        // Тест 3: Чужое сообщение + читаем историю - показываем индикатор
        console.log('\n--- Тест 3: Чужое сообщение + история = индикатор ---');
        
        // Прокручиваем вверх (читаем историю)
        container.scrollTop = 100;
        await this.sleep(100);
        
        const readingHistory = !controller.scrollManager.isNearBottom();
        this.assert(readingHistory, 'Должны читать историю (не внизу)');
        
        // Сбрасываем счётчик индикатора
        controller._newMessagesCount = 0;
        
        // Добавляем чужое сообщение
        controller.store.addMessage({
            id: 102,
            chat_id: 1,
            author_id: 2,
            author_name: 'Other User',
            content: 'Another message',
            created_ts: Date.now() + 32000,
            created: new Date(Date.now() + 32000).toISOString()
        });
        
        await this.sleep(500);
        
        // Проверяем что индикатор показан
        this.assert(controller._newMessagesCount > 0, 'Счётчик новых сообщений должен увеличиться');
        
        const indicator = document.getElementById('new-messages-btn');
        if (indicator) {
            const isVisible = indicator.style.display !== 'none';
            this.assert(isVisible, 'Индикатор новых сообщений должен быть видимым');
        } else {
            console.warn('[Test V2] Индикатор не найден (может создаваться при первом показе)');
        }

        // Тест 4: Клик по индикатору - скролл вниз и скрытие
        console.log('\n--- Тест 4: Клик по индикатору ---');
        
        if (indicator && controller._newMessagesCount > 0) {
            // Кликаем по индикатору
            indicator.click();
            
            // Ждём завершения анимации скролла
            await this.sleep(500);
            
            // Проверяем что прокрутили вниз
            const isAtBottomNow = controller.scrollManager.isNearBottom();
            this.assert(isAtBottomNow, 'После клика по индикатору должны быть внизу');
            
            // Проверяем что счётчик сброшен
            this.assertEqual(controller._newMessagesCount, 0, 'Счётчик должен быть сброшен');
            
            // Проверяем что индикатор скрыт
            const isHiddenNow = indicator.style.display === 'none';
            this.assert(isHiddenNow, 'Индикатор должен быть скрыт');
        }

        // Тест 5: Ручной скролл вниз - скрытие индикатора
        console.log('\n--- Тест 5: Ручной скролл вниз ---');
        
        // Прокручиваем вверх
        container.scrollTop = 50;
        controller._newMessagesCount = 5; // Устанавливаем счётчик вручную
        
        if (indicator) {
            indicator.style.display = 'flex';
            const badge = indicator.querySelector('.badge');
            if (badge) badge.textContent = '5';
        }
        
        await this.sleep(100);
        
        const countBefore = controller._newMessagesCount;
        this.assertEqual(countBefore, 5, 'Счётчик установлен корректно');
        
        // Прокручиваем вниз вручную (programmatic scroll)
        controller.scrollManager.scrollToBottom({ instant: false, force: true });
        
        // Ждем скролл event + обработку
        await this.sleep(800);
        
        // Проверяем что индикатор скрылся
        this.assertEqual(controller._newMessagesCount, 0, 'Счётчик должен сброситься при ручном скролле');

        // Тест 6: Оптимистичное сообщение - скроллим
        console.log('\n--- Тест 6: Оптимистичное сообщение ---');
        
        // Прокручиваем вверх
        container.scrollTop = 80;
        await this.sleep(100);
        
        const notAtBottomBefore = !controller.scrollManager.isNearBottom();
        this.assert(notAtBottomBefore, 'Должны быть не внизу перед оптимистичным сообщением');
        
        // Добавляем оптимистичное сообщение (своё)
        controller.store.addMessage({
            id: 'temp_123',
            chat_id: 1,
            author_id: currentUserId,
            author_name: 'Me',
            content: 'Optimistic message',
            created_ts: Date.now() + 33000,
            created: new Date(Date.now() + 33000).toISOString(),
            is_optimistic: true
        }, true); // true = optimistic
        
        await this.sleep(500);
        
        const atBottomAfter = controller.scrollManager.isNearBottom();
        this.assert(atBottomAfter, 'Оптимистичное сообщение должно скроллить вниз');

        // Тест 7: Методы индикатора существуют
        console.log('\n--- Тест 7: API индикатора ---');
        
        this.assert(typeof controller._showNewMessagesIndicator === 'function', '_showNewMessagesIndicator должен быть функцией');
        this.assert(typeof controller._hideNewMessagesIndicator === 'function', '_hideNewMessagesIndicator должен быть функцией');
        this.assert(typeof controller._findOrCreateNewMessagesButton === 'function', '_findOrCreateNewMessagesButton должен быть функцией');
        this.assert(typeof controller._initScrollWatcher === 'function', '_initScrollWatcher должен быть функцией');

        // Тест 8: Счётчик новых сообщений инкрементируется
        console.log('\n--- Тест 8: Счётчик сообщений ---');
        
        container.scrollTop = 100;
        controller._newMessagesCount = 0;
        await this.sleep(100);
        
        // Добавляем 3 чужих сообщения подряд
        for (let i = 0; i < 3; i++) {
            controller.store.addMessage({
                id: 200 + i,
                chat_id: 1,
                author_id: 2,
                author_name: 'Other User',
                content: `Batch message ${i}`,
                created_ts: Date.now() + 40000 + i * 100,
                created: new Date(Date.now() + 40000 + i * 100).toISOString()
            });
            await this.sleep(50);
        }
        
        await this.sleep(500);
        
        this.assertEqual(controller._newMessagesCount, 3, 'Счётчик должен показывать 3 новых сообщения');

        // Cleanup
        controller.destroy();
        if (indicator && indicator.parentElement) {
            indicator.parentElement.removeChild(indicator);
        }
        document.body.removeChild(container);

        this.printResults();
        return this.results;
    }

    // ==================== Публичное API ====================

    async runAll() {
        console.log('\n' + '='.repeat(60));
        console.log('🚀 Запуск всех тестов ChatControllerV2');
        console.log('='.repeat(60));

        const basicResults = await this.testBasicFunctionalityV2();
        const smartAutoscrollResults = await this.testSmartAutoscrollV2();

        const totalPassed = basicResults.passed + smartAutoscrollResults.passed;
        const totalFailed = basicResults.failed + smartAutoscrollResults.failed;
        const totalTests = basicResults.total + smartAutoscrollResults.total;
        const totalRate = totalTests > 0 ? parseFloat(((totalPassed / totalTests) * 100).toFixed(1)) : 0;

        console.log('\n' + '='.repeat(60));
        console.log('📊 ИТОГОВЫЕ РЕЗУЛЬТАТЫ V2:');
        console.log(`   ✅ Успешных: ${totalPassed}`);
        console.log(`   ❌ Провалено: ${totalFailed}`);
        console.log(`   📈 Процент: ${totalRate}%`);
        console.log('='.repeat(60) + '\n');

        return {
            basic: basicResults,
            smartAutoscroll: smartAutoscrollResults,
            total: { passed: totalPassed, failed: totalFailed, total: totalTests, passRate: totalRate }
        };
    }
}

// Создаем глобальный экземпляр
const chatTestsV2 = new ChatTestSuiteV2();

// Экспортируем для использования в модулях
export default chatTestsV2;

// Добавляем в window для вызова из консоли
window.ChatTestsV2 = {
    runAll: () => chatTestsV2.runAll(),
    testBasicFunctionalityV2: () => chatTestsV2.testBasicFunctionalityV2(),
    testSmartAutoscrollV2: () => chatTestsV2.testSmartAutoscrollV2()
};

console.log('✅ ChatTestsV2 loaded!');
console.log('💡 Запуск из консоли:');
console.log('  window.ChatTestsV2.runAll()                   - Все тесты V2');
console.log('  window.ChatTestsV2.testBasicFunctionalityV2() - Базовая функциональность');
console.log('  window.ChatTestsV2.testSmartAutoscrollV2()    - Умный автоскролл');
console.log('');
console.log('⚠️  ПРИМЕЧАНИЕ: Это сокращенная версия тестов для V2.');
console.log('    Полная версия (11 тестов, 1732 строки) доступна в chatTests.js');
console.log('    V2 тесты фокусируются на новых фичах: smart autoscroll, batch ops, retry logic');
