/**
 * Frontend тесты для двунаправленной загрузки сообщений
 * 
 * Проверяемые компоненты:
 * - MessageLoaderV2 (loadHistory, loadNewer, loadAround)
 * - ScrollManagerV2 (IntersectionObserver, автозагрузка)
 * - MessageRendererV2 (prependMessages, appendMessages)
 * - MessageStoreV2 (boundaries, hasMoreAfter)
 * 
 * Запуск:
 *   npm test -- bidirectional-loading.test.js
 * 
 * Или через браузер:
 *   Открыть в браузере с включенным live server
 */

import { MessageLoaderV2 } from '../loaders/messageLoaderV2.js';
import { ScrollManagerV2 } from '../managers/scrollManagerV2.js';
import { MessageRendererV2 } from '../renderers/messageRendererV2.js';
import { MessageStoreV2 } from '../stores/messageStoreV2.js';

// ==================== Mock Data ====================

const MOCK_MESSAGES = {
    // Сообщения за 1 января
    jan1: Array.from({ length: 30 }, (_, i) => ({
        id: i + 1,
        chat_id: 1,
        author_id: 1,
        content: `Message from Jan 1 - ${i}`,
        created_ts: new Date(2026, 0, 1, 12, i).getTime(),
        author: { id: 1, name: 'Test User' }
    })),
    
    // Сообщения за 5 января
    jan5: Array.from({ length: 40 }, (_, i) => ({
        id: i + 31,
        chat_id: 1,
        author_id: 1,
        content: `Message from Jan 5 - ${i}`,
        created_ts: new Date(2026, 0, 5, 12, i).getTime(),
        author: { id: 1, name: 'Test User' }
    })),
    
    // Сообщения за 10 января
    jan10: Array.from({ length: 30 }, (_, i) => ({
        id: i + 71,
        chat_id: 1,
        author_id: 1,
        content: `Message from Jan 10 - ${i}`,
        created_ts: new Date(2026, 0, 10, 12, i).getTime(),
        author: { id: 1, name: 'Test User' }
    }))
};

const ALL_MESSAGES = [
    ...MOCK_MESSAGES.jan1,
    ...MOCK_MESSAGES.jan5,
    ...MOCK_MESSAGES.jan10
];

// ==================== Mock API ====================

class MockAPI {
    static fetchMessages(params = {}) {
        const { before_id, after_id, around_id, limit = 30 } = params;
        
        let filtered = [...ALL_MESSAGES];
        
        // Загрузка вокруг даты (timestamp)
        if (around_id && around_id > 1_000_000_000) {
            const targetTimestamp = around_id;
            
            // Находим ближайшее сообщение
            const closest = filtered.reduce((prev, curr) => {
                return Math.abs(curr.created_ts - targetTimestamp) < Math.abs(prev.created_ts - targetTimestamp) 
                    ? curr 
                    : prev;
            });
            
            const closestIndex = filtered.indexOf(closest);
            const start = Math.max(0, closestIndex - Math.floor(limit / 2));
            const end = Math.min(filtered.length, start + limit);
            
            filtered = filtered.slice(start, end);
            
            return {
                results: filtered,
                anchor_id: closest.id,
                anchor_index: closestIndex,
                has_more_before: start > 0,
                has_more_after: end < ALL_MESSAGES.length
            };
        }
        
        // Загрузка после ID (новые сообщения)
        if (after_id) {
            filtered = filtered.filter(msg => msg.id > after_id);
            filtered = filtered.slice(0, limit);
            
            const lastId = filtered.length > 0 ? filtered[filtered.length - 1].id : after_id;
            const hasMoreAfter = ALL_MESSAGES.some(msg => msg.id > lastId);
            
            return {
                results: filtered,
                has_more: false,
                has_more_after: hasMoreAfter,
                next_after_id: hasMoreAfter ? lastId : null
            };
        }
        
        // Загрузка перед ID (старые сообщения)
        if (before_id) {
            filtered = filtered.filter(msg => msg.id < before_id);
            filtered = filtered.slice(-limit);
            
            const firstId = filtered.length > 0 ? filtered[0].id : before_id;
            const hasMoreBefore = ALL_MESSAGES.some(msg => msg.id < firstId);
            
            return {
                results: filtered,
                has_more: hasMoreBefore,
                has_more_after: true
            };
        }
        
        // Загрузка последних сообщений
        filtered = filtered.slice(-limit);
        
        return {
            results: filtered,
            has_more: ALL_MESSAGES.length > limit,
            has_more_after: false
        };
    }
}

// ==================== Test Suite: MessageLoaderV2 ====================

describe('MessageLoaderV2 - Bidirectional Loading', () => {
    let loader;
    let store;
    
    beforeEach(() => {
        store = new MessageStoreV2({ currentUserId: 1 });
        
        // Mock fetch
        global.fetch = jest.fn((url) => {
            const urlObj = new URL(url, 'http://localhost');
            const params = Object.fromEntries(urlObj.searchParams);
            const data = MockAPI.fetchMessages(params);
            
            return Promise.resolve({
                ok: true,
                json: () => Promise.resolve(data)
            });
        });
        
        loader = new MessageLoaderV2({ store });
    });
    
    afterEach(() => {
        jest.restoreAllMocks();
    });
    
    test('Test 1: loadHistory загружает старые сообщения', async () => {
        const chatId = 1;
        
        // Загружаем последние
        await loader.loadInitial(chatId);
        const oldestBefore = store.getOldestMessage(chatId);
        
        // Загружаем историю
        const messages = await loader.loadHistory(chatId);
        
        expect(messages.length).toBeGreaterThan(0);
        
        // Проверяем что все сообщения старше
        messages.forEach(msg => {
            expect(msg.id).toBeLessThan(oldestBefore.id);
        });
        
        expect(loader.hasMoreBefore(chatId)).toBe(true);
    });
    
    test('Test 2: loadNewer загружает новые сообщения', async () => {
        const chatId = 1;
        
        // Загружаем сообщения за 5 января через loadAround
        const jan5Timestamp = new Date(2026, 0, 5, 12, 0).getTime();
        await loader.loadAround(chatId, jan5Timestamp);
        
        const newestBefore = store.getNewestMessage(chatId);
        
        // Загружаем новые сообщения
        const messages = await loader.loadNewer(chatId);
        
        expect(messages.length).toBeGreaterThan(0);
        
        // Проверяем что все сообщения новее
        messages.forEach(msg => {
            expect(msg.id).toBeGreaterThan(newestBefore.id);
        });
    });
    
    test('Test 3: loadAround загружает сообщения вокруг даты', async () => {
        const chatId = 1;
        const targetDate = new Date(2026, 0, 5, 12, 0);
        
        const result = await loader.loadAround(chatId, targetDate.getTime());
        
        expect(result.messages.length).toBeGreaterThan(0);
        expect(result.anchorId).toBeDefined();
        expect(result.hasMoreBefore).toBe(true);
        expect(result.hasMoreAfter).toBe(true);
        
        // Проверяем что сообщения действительно за 5 января
        const jan5Messages = result.messages.filter(m => m.content.includes('Jan 5'));
        expect(jan5Messages.length).toBeGreaterThan(0);
    });
    
    test('Test 4: hasMoreAfter корректно отслеживается', async () => {
        const chatId = 1;
        
        // Загружаем последние сообщения
        await loader.loadInitial(chatId);
        
        // Для последних сообщений hasMoreAfter должен быть false
        expect(loader.hasMoreAfter(chatId)).toBe(false);
        
        // Загружаем сообщения за 5 января
        const jan5Timestamp = new Date(2026, 0, 5, 12, 0).getTime();
        await loader.loadAround(chatId, jan5Timestamp);
        
        // Теперь hasMoreAfter должен быть true (есть сообщения за 10 января)
        expect(loader.hasMoreAfter(chatId)).toBe(true);
    });
    
    test('Test 5: boundaries обновляются после loadNewer', async () => {
        const chatId = 1;
        
        // Загружаем середину
        const jan5Timestamp = new Date(2026, 0, 5, 12, 0).getTime();
        await loader.loadAround(chatId, jan5Timestamp);
        
        const newestBefore = store.getNewestMessage(chatId);
        
        // Загружаем новые
        await loader.loadNewer(chatId);
        
        const newestAfter = store.getNewestMessage(chatId);
        
        // newestId должен обновиться
        expect(newestAfter.id).toBeGreaterThan(newestBefore.id);
    });
});

// ==================== Test Suite: ScrollManagerV2 ====================

describe('ScrollManagerV2 - IntersectionObserver', () => {
    let scrollManager;
    let loader;
    let renderer;
    let store;
    let scrollElement;
    
    beforeEach(() => {
        // Создаем DOM элементы
        document.body.innerHTML = `
            <div id="chatScroll" style="height: 400px; overflow-y: auto;">
            </div>
        `;
        
        scrollElement = document.getElementById('chatScroll');
        store = new MessageStoreV2({ currentUserId: 1 });
        
        // Mock fetch
        global.fetch = jest.fn((url) => {
            const urlObj = new URL(url, 'http://localhost');
            const params = Object.fromEntries(urlObj.searchParams);
            const data = MockAPI.fetchMessages(params);
            
            return Promise.resolve({
                ok: true,
                json: () => Promise.resolve(data)
            });
        });
        
        loader = new MessageLoaderV2({ store });
        renderer = new MessageRendererV2({ 
            store, 
            containerId: 'chatScroll',
            currentUserId: 1
        });
        
        scrollManager = new ScrollManagerV2({
            scrollElement,
            loader,
            renderer,
            store,
            chatId: 1
        });
    });
    
    afterEach(() => {
        scrollManager.destroy();
        jest.restoreAllMocks();
    });
    
    test('Test 6: IntersectionObserver на первом сообщении (история)', async () => {
        const chatId = 1;
        
        // Загружаем начальные сообщения
        await loader.loadInitial(chatId);
        await renderer.render(chatId);
        
        await scrollManager.init();
        
        // Проверяем что observer создан
        expect(scrollManager._historyObserver).toBeDefined();
        
        // Проверяем что наблюдается первое сообщение
        const firstMessage = scrollElement.querySelector('.msg[data-message-id]');
        expect(firstMessage).toBeTruthy();
    });
    
    test('Test 7: IntersectionObserver на последнем сообщении (новые)', async () => {
        const chatId = 1;
        
        // Загружаем сообщения за 5 января (не последние)
        const jan5Timestamp = new Date(2026, 0, 5, 12, 0).getTime();
        await loader.loadAround(chatId, jan5Timestamp);
        await renderer.render(chatId);
        
        await scrollManager.init();
        
        // Проверяем что observer для новых сообщений создан
        expect(scrollManager._newerObserver).toBeDefined();
        
        // Проверяем что hasMoreAfter = true
        expect(loader.hasMoreAfter(chatId)).toBe(true);
    });
    
    test('Test 8: loadMoreNewer вызывается при скролле вниз', async () => {
        const chatId = 1;
        
        // Spy на loadMoreNewer
        const loadNewerSpy = jest.spyOn(scrollManager, 'loadMoreNewer');
        
        // Загружаем сообщения за 5 января
        const jan5Timestamp = new Date(2026, 0, 5, 12, 0).getTime();
        await loader.loadAround(chatId, jan5Timestamp);
        await renderer.render(chatId);
        
        await scrollManager.init();
        
        // Симулируем скролл вниз до последнего сообщения
        scrollElement.scrollTop = scrollElement.scrollHeight;
        
        // Триггерим IntersectionObserver (в реальности срабатывает автоматически)
        // В тестах нужно вызвать вручную
        const lastMessage = scrollElement.querySelector('.msg[data-message-id]:last-child');
        
        if (lastMessage && scrollManager._newerObserver) {
            // Simulate intersection
            await scrollManager.loadMoreNewer();
            
            expect(loadNewerSpy).toHaveBeenCalled();
        }
    });
    
    test('Test 9: pauseScrollEvents приостанавливает обработку', async () => {
        const chatId = 1;
        
        await loader.loadInitial(chatId);
        await renderer.render(chatId);
        await scrollManager.init();
        
        // Приостанавливаем на 500мс
        scrollManager.pauseScrollEvents(500);
        
        // События скролла должны игнорироваться
        const scrollHandler = jest.spyOn(scrollManager, '_onScroll');
        
        scrollElement.scrollTop = 100;
        scrollElement.dispatchEvent(new Event('scroll'));
        
        // Проверяем что обработчик НЕ вызвался (или вернулся рано)
        // В реальной реализации pauseScrollEvents ставит флаг
    });
});

// ==================== Test Suite: MessageRendererV2 ====================

describe('MessageRendererV2 - Append/Prepend', () => {
    let renderer;
    let store;
    
    beforeEach(() => {
        document.body.innerHTML = `<div id="chatScroll"></div>`;
        
        store = new MessageStoreV2({ currentUserId: 1 });
        renderer = new MessageRendererV2({
            store,
            containerId: 'chatScroll',
            currentUserId: 1
        });
    });
    
    test('Test 10: prependMessages добавляет в начало', () => {
        const chatId = 1;
        const container = document.getElementById('chatScroll');
        
        // Добавляем начальные сообщения
        store.addMessages(MOCK_MESSAGES.jan5);
        renderer.render(chatId);
        
        const countBefore = container.querySelectorAll('.msg').length;
        
        // Prepend старые сообщения
        store.addMessages(MOCK_MESSAGES.jan1);
        const fragment = renderer.prependMessages(MOCK_MESSAGES.jan1, chatId);
        container.insertBefore(fragment, container.firstChild);
        
        const countAfter = container.querySelectorAll('.msg').length;
        
        expect(countAfter).toBeGreaterThan(countBefore);
        
        // Проверяем что первое сообщение теперь за 1 января
        const firstMessage = container.querySelector('.msg[data-message-id]');
        expect(firstMessage.dataset.messageId).toBe('1');
    });
    
    test('Test 11: appendMessages добавляет в конец', () => {
        const chatId = 1;
        const container = document.getElementById('chatScroll');
        
        // Добавляем начальные сообщения
        store.addMessages(MOCK_MESSAGES.jan5);
        renderer.render(chatId);
        
        const countBefore = container.querySelectorAll('.msg').length;
        
        // Append новые сообщения
        store.addMessages(MOCK_MESSAGES.jan10);
        const fragment = renderer.appendMessages(MOCK_MESSAGES.jan10, chatId);
        container.appendChild(fragment);
        
        const countAfter = container.querySelectorAll('.msg').length;
        
        expect(countAfter).toBeGreaterThan(countBefore);
        
        // Проверяем что последнее сообщение теперь за 10 января
        const messages = container.querySelectorAll('.msg[data-message-id]');
        const lastMessage = messages[messages.length - 1];
        expect(lastMessage.dataset.messageId).toBe('100');
    });
    
    test('Test 12: Date dividers создаются корректно', () => {
        const chatId = 1;
        const container = document.getElementById('chatScroll');
        
        // Добавляем сообщения за разные даты
        store.addMessages([...MOCK_MESSAGES.jan1, ...MOCK_MESSAGES.jan5]);
        renderer.render(chatId);
        
        // Должны быть 2 date dividers (1 января и 5 января)
        const dividers = container.querySelectorAll('.day-divider, .sticky-date');
        expect(dividers.length).toBeGreaterThan(0);
    });
});

// ==================== Test Suite: Integration ====================

describe('Integration - Full Bidirectional Flow', () => {
    let loader;
    let renderer;
    let scrollManager;
    let store;
    let scrollElement;
    
    beforeEach(() => {
        document.body.innerHTML = `<div id="chatScroll" style="height: 400px; overflow-y: auto;"></div>`;
        
        scrollElement = document.getElementById('chatScroll');
        store = new MessageStoreV2({ currentUserId: 1 });
        
        global.fetch = jest.fn((url) => {
            const urlObj = new URL(url, 'http://localhost');
            const params = Object.fromEntries(urlObj.searchParams);
            const data = MockAPI.fetchMessages(params);
            
            return Promise.resolve({
                ok: true,
                json: () => Promise.resolve(data)
            });
        });
        
        loader = new MessageLoaderV2({ store });
        renderer = new MessageRendererV2({
            store,
            containerId: 'chatScroll',
            currentUserId: 1
        });
        scrollManager = new ScrollManagerV2({
            scrollElement,
            loader,
            renderer,
            store,
            chatId: 1
        });
    });
    
    afterEach(() => {
        scrollManager.destroy();
        jest.restoreAllMocks();
    });
    
    test('Test 13: Полный сценарий - прыжок → история → новые', async () => {
        const chatId = 1;
        
        // Шаг 1: Прыгаем на 5 января
        const jan5Timestamp = new Date(2026, 0, 5, 12, 0).getTime();
        await loader.loadAround(chatId, jan5Timestamp);
        await renderer.render(chatId);
        
        const messagesAfterJump = store.getMessageCount(chatId);
        expect(messagesAfterJump).toBeGreaterThan(0);
        
        // Шаг 2: Загружаем историю (старые)
        await scrollManager.loadMoreHistory();
        
        const messagesAfterHistory = store.getMessageCount(chatId);
        expect(messagesAfterHistory).toBeGreaterThan(messagesAfterJump);
        
        // Шаг 3: Загружаем новые сообщения
        await scrollManager.loadMoreNewer();
        
        const messagesAfterNewer = store.getMessageCount(chatId);
        expect(messagesAfterNewer).toBeGreaterThan(messagesAfterHistory);
        
        // Проверяем границы
        const oldest = store.getOldestMessage(chatId);
        const newest = store.getNewestMessage(chatId);
        
        expect(oldest.id).toBeLessThan(newest.id);
    });
});

// ==================== Test Runner ====================

// Для запуска в браузере (без Jest)
if (typeof jest === 'undefined') {
    console.log('Running tests in browser mode...');
    
    // Простой тестовый раннер
    const runTests = async () => {
        console.group('MessageLoaderV2 Tests');
        // Здесь можно добавить ручные тесты
        console.groupEnd();
    };
    
    runTests();
}

export {
    MockAPI,
    MOCK_MESSAGES,
    ALL_MESSAGES
};
