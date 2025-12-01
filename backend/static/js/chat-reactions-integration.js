// backend/static/js/chat-reactions-integration.js
/**
 * Интеграция реакций с WebSocket для чата
 * Обрабатывает только события WebSocket: chat:reaction-added и chat:reaction-removed
 * Рендеринг реакций для новых сообщений делается в chat-detail-enhanced.js через MutationObserver
 */

import MessageReactions from './components/messageReactions.js';

console.log('[Reactions Integration] ========== MODULE LOADED ==========');
console.log('[Reactions Integration] window.chatWebSocketApi:', window.chatWebSocketApi);
console.log('[Reactions Integration] window.currentUserId:', window.currentUserId);
console.log('[Reactions Integration] document.body.dataset.userId:', document.body.dataset.userId);

// Функция инициализации
function initReactionsIntegration() {
    console.log('[Reactions Integration] Initializing...');
    
    // Получаем текущего пользователя (предполагается, что ID доступен)
    const currentUserId = window.currentUserId || parseInt(document.body.dataset.userId);
    
    if (!currentUserId) {
        console.error('[Reactions Integration] Current user ID not found. Reactions will not work properly.');
        return;
    }

    console.log('[Reactions Integration] Current user ID:', currentUserId);

    // Создаём экземпляр MessageReactions
    const reactions = new MessageReactions({
        apiBaseUrl: '/api/v1/communications/messages',
        emojis: ['👍', '❤️', '😂', '😮', '😢', '🙏', '👏', '🔥', '🎉', '🤔'],
        getCsrfToken: () => {
            const cookie = document.cookie
                .split('; ')
                .find(row => row.startsWith('csrftoken='));
            return cookie ? cookie.split('=')[1] : '';
        }
    });

    // Обработка WebSocket событий реакций
    window.addEventListener('chat:reaction-added', (event) => {
        console.log('[Reactions Integration] ✓ WebSocket event received: reaction-added', event.detail);
        reactions.handleReactionAdded(event.detail, currentUserId);
    });

    window.addEventListener('chat:reaction-removed', (event) => {
        console.log('[Reactions Integration] ✓ WebSocket event received: reaction-removed', event.detail);
        reactions.handleReactionRemoved(event.detail, currentUserId);
    });

    // Экспортируем для использования в других скриптах
    window.MessageReactions = reactions;

    console.log('[Reactions Integration] ✓ Initialized successfully. Listening for WebSocket events.');
}

// Ждём, когда WebSocket будет готов
if (window.chatWebSocketApi) {
    console.log('[Reactions Integration] WebSocket already ready, initializing immediately');
    initReactionsIntegration();
} else {
    console.log('[Reactions Integration] Waiting for WebSocket to be ready...');
    window.addEventListener('chat:ws-ready', () => {
        console.log('[Reactions Integration] WebSocket ready event received');
        initReactionsIntegration();
    });
}
