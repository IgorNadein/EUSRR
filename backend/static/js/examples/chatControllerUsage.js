/**
 * @fileoverview Пример использования новой архитектуры
 * 
 * Демонстрирует как использовать ChatController
 * вместо старых разрозненных модулей
 */

import { ChatController } from './controllers/chatController.js';

// ==================== СТАРЫЙ СПОСОБ (deprecated) ====================

/*
// Было раньше - много разных модулей:
import { initUserWebSocket } from './components/userWebSocket.js';
import { MessageRenderer } from './components/messageRenderer.js';
import { initChatHistoryLoader } from './components/chatHistoryLoader.js';
import { initChatMarkRead } from './components/chatMarkRead.js';

const scrollEl = document.getElementById('chatScroll');
const chatId = parseInt(scrollEl.dataset.chatId);

// Создаем renderer
const messageRenderer = new MessageRenderer({
    containerId: 'chatScroll',
    currentUserId: userId,
    profileUrl: profileUrl,
    detailUrlTemplate: detailUrlTemplate
});

// Инициализируем WebSocket
const userWs = initUserWebSocket({ userId });
userWs.configure({
    chatId,
    messageRenderer,
    scrollContainerId: 'chatScroll'
});

// Инициализируем History Loader
initChatHistoryLoader({
    messageRenderer,
    scrollContainerId: 'chatScroll',
    fetchUrl: `/api/v1/communications/chats/${chatId}/messages/`
});

// И еще кучу других модулей...
*/

// ==================== НОВЫЙ СПОСОБ (recommended) ====================

/**
 * Инициализация чата с новой архитектурой
 */
async function initChat() {
    // Получаем данные из DOM
    const scrollEl = document.getElementById('chatScroll');
    const chatId = parseInt(scrollEl.dataset.chatId);
    const currentUserId = parseInt(document.body.dataset.userId);

    // Получаем WebSocket (он уже инициализирован в base.html)
    const ws = window.userWebSocket;

    // Создаем ChatController - ВСЁ в одном!
    const chatController = new ChatController({
        chatId,
        currentUserId,
        scrollElement: scrollEl,
        containerId: 'chatScroll',
        wsConnection: ws,
        profileUrl: '/employees/profile/',
        detailUrlTemplate: '/employees/detail/0/'
    });

    // Инициализируем (загрузка + рендеринг + scroll)
    await chatController.init();

    // Готово! ChatController управляет всем:
    // - MessageStore (хранилище)
    // - MessageLoader (загрузка)
    // - MessageRenderer (рендеринг)
    // - ScrollManager (прокрутка)

    // Экспортируем в window для доступа из других модулей
    window.chatController = chatController;

    console.log('✅ Chat initialized with new architecture!');
    console.log('Status:', chatController.getStatus());
}

// ==================== ИСПОЛЬЗОВАНИЕ ====================

/**
 * Отправка сообщения
 */
function sendMessage() {
    const textarea = document.getElementById('messageInput');
    const content = textarea.value.trim();

    if (!content) return;

    // Просто вызываем метод контроллера
    const tempId = window.chatController.sendMessage(content);
    
    console.log('Message sent with temp ID:', tempId);
    
    // Очищаем textarea
    textarea.value = '';
}

/**
 * Прокрутка к последнему сообщению
 */
function scrollToLatest() {
    window.chatController.scrollToBottom({ instant: false });
}

/**
 * Загрузка истории
 */
async function loadMore() {
    const messages = await window.chatController.loadMoreHistory();
    console.log('Loaded', messages.length, 'historical messages');
}

/**
 * Получение статуса чата
 */
function getStatus() {
    const status = window.chatController.getStatus();
    console.log('Chat status:', status);
    return status;
}

/**
 * Поиск сообщения
 */
function findMessage(messageId) {
    const message = window.chatController.getMessage(messageId);
    console.log('Message:', message);
    return message;
}

/**
 * Прокрутка к конкретному сообщению
 */
function goToMessage(messageId) {
    window.chatController.scrollToMessage(messageId, {
        block: 'center',
        behavior: 'smooth'
    });
}

// ==================== ИНТЕГРАЦИЯ С ДРУГИМИ МОДУЛЯМИ ====================

/**
 * Интеграция с ChatComposer
 */
function integrateChatComposer() {
    // ChatComposer теперь может использовать ChatController
    const composer = {
        sendMessage: (content, options) => {
            return window.chatController.sendMessage(content, options);
        },
        
        isNearBottom: () => {
            return window.chatController.isNearBottom();
        }
    };
    
    return composer;
}

/**
 * Интеграция с реакциями (reactions)
 */
window.addEventListener('chat:message-added', (event) => {
    const { messageId, chatId } = event.detail;
    
    // Инициализируем реакции для нового сообщения
    console.log('New message added, initializing reactions:', messageId);
    
    // MessageContextMenu автоматически подхватит через MutationObserver
});

/**
 * Интеграция с уведомлениями о прочтении
 */
window.addEventListener('chat:message-added', (event) => {
    const { messageId } = event.detail;
    
    // Проверяем видимо ли сообщение
    const isVisible = window.chatController.scrollManager.isNearBottom();
    
    if (isVisible) {
        // Отмечаем как прочитанное
        // markAsRead(messageId);
    }
});

// ==================== ЭКСПОРТ ====================

export {
    initChat,
    sendMessage,
    scrollToLatest,
    loadMore,
    getStatus,
    findMessage,
    goToMessage,
    integrateChatComposer
};

// Автозапуск если это страница чата
if (document.getElementById('chatScroll')) {
    // Ждем когда DOM полностью загрузится
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initChat);
    } else {
        initChat();
    }
}
