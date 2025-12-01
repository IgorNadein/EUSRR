/**
 * Enhanced Chat Detail - только UI компоненты (реакции, контекстное меню, выделение, голосования)
 * WebSocket управление вынесено в chatWebSocket.js (base.html)
 */
import MessageReactions from './components/messageReactions.js';
import MessageContextMenu from './components/messageContextMenu.js';
import MessageSelection from './components/messageSelection.js';
import ChatPoll from './components/chatPoll.js';
import { initMessageEditing } from './components/messageEditing.js';
import reactionsConfig from './config/reactionsConfig.js';

console.log('[chat-detail-enhanced] Script loaded');

// Защита от повторной инициализации
if (window.__CHAT_DETAIL_ENHANCED_INITIALIZED__) {
    console.warn('chat-detail-enhanced.js: already initialized, skipping');
} else {
    console.log('[chat-detail-enhanced] Starting initialization...');
    window.__CHAT_DETAIL_ENHANCED_INITIALIZED__ = true;

// Главная функция инициализации
async function initChatDetail() {
    'use strict';

    const chatScroll = document.getElementById('chatScroll');
    console.log('[chat-detail-enhanced] chatScroll element:', chatScroll);
    if (!chatScroll) return;

    const chatId = chatScroll.dataset.chatId;
    const meId = parseInt(chatScroll.dataset.meId);
    console.log('[chat-detail-enhanced] chatId:', chatId, 'meId:', meId);
    
    // Загружаем доступные реакции из БД
    console.log('[chat-detail-enhanced] Loading available reactions from API...');
    await reactionsConfig.load();
    const availableEmojis = reactionsConfig.getEmojis();
    console.log('[chat-detail-enhanced] ✓ Available emojis:', availableEmojis);
    
    // Инициализируем систему реакций
    const reactions = new MessageReactions();
    console.log('[chat-detail-enhanced] MessageReactions initialized');
    
    // Инициализируем обработку редактирования сообщений
    initMessageEditing();
    console.log('[chat-detail-enhanced] Message editing initialized');
    
    // Инициализируем систему выделения сообщений
    console.log('[chat-detail-enhanced] Initializing MessageSelection...');
    const messageSelection = new MessageSelection({
        chatId: chatId,
        scrollContainerId: 'chatScroll',
        currentUserId: String(meId),
        onForward: (messageIds, targetChatId) => {
            console.log('Messages forwarded:', messageIds, 'to chat:', targetChatId);
        }
    });
    console.log('[chat-detail-enhanced] MessageSelection initialized');
    
    // Инициализируем систему голосований
    const chatPoll = new ChatPoll({
        chatId: chatId
    });
    console.log('[chat-detail-enhanced] ChatPoll initialized');
    
    // Делаем доступным глобально для использования в других модулях
    window.chatPoll = chatPoll;
    
    // ==================== WebSocket ОБРАБОТЧИКИ РЕАКЦИЙ ====================
    
    // Обработка добавления реакции через WebSocket
    window.addEventListener('chat:reaction-added', (event) => {
        console.log('[chat-detail-enhanced] WebSocket: reaction-added', event.detail);
        const data = event.detail;
        const messageId = data.message_id || data.messageId;
        
        console.log('[chat-detail-enhanced] Looking for message ID:', messageId);
        console.log('[chat-detail-enhanced] Reactions summary:', data.reactions_summary);
        
        const messageElements = document.querySelectorAll(`[data-message-id="${messageId}"]`);
        console.log('[chat-detail-enhanced] Found message elements:', messageElements.length);
        
        if (messageElements.length && data.reactions_summary) {
            messageElements.forEach(messageElement => {
                console.log('[chat-detail-enhanced] Updating message element:', messageElement);
                
                // Обновляем data-атрибут с реакциями
                messageElement.dataset.reactions = JSON.stringify(data.reactions_summary);
                
                // Обновляем отображение
                const wrapper = messageElement.querySelector('.message-reactions-wrapper');
                if (wrapper) {
                    const reactionsHtml = reactions.renderReactions(data.reactions_summary, meId);
                    wrapper.innerHTML = reactionsHtml;
                    reactions.initMessageReactions(messageElement, messageId, meId);
                    console.log('[chat-detail-enhanced] ✓ Reactions updated successfully');
                } else {
                    console.warn('[chat-detail-enhanced] ✗ Wrapper not found in message');
                }
            });
        } else {
            if (!data.reactions_summary) {
                console.warn('[chat-detail-enhanced] ✗ No reactions_summary in WebSocket data');
            }
            if (!messageElements.length) {
                console.warn('[chat-detail-enhanced] ✗ Message element not found for ID:', messageId);
            }
        }
    });
    
    // Обработка удаления реакции через WebSocket
    window.addEventListener('chat:reaction-removed', (event) => {
        console.log('[chat-detail-enhanced] WebSocket: reaction-removed', event.detail);
        const data = event.detail;
        const messageId = data.message_id || data.messageId;
        
        console.log('[chat-detail-enhanced] Looking for message ID:', messageId);
        console.log('[chat-detail-enhanced] Reactions summary:', data.reactions_summary);
        
        const messageElements = document.querySelectorAll(`[data-message-id="${messageId}"]`);
        console.log('[chat-detail-enhanced] Found message elements:', messageElements.length);
        
        if (messageElements.length && data.reactions_summary) {
            messageElements.forEach(messageElement => {
                console.log('[chat-detail-enhanced] Updating message element:', messageElement);
                
                // Обновляем data-атрибут с реакциями
                messageElement.dataset.reactions = JSON.stringify(data.reactions_summary);
                
                // Обновляем отображение
                const wrapper = messageElement.querySelector('.message-reactions-wrapper');
                if (wrapper) {
                    const reactionsHtml = reactions.renderReactions(data.reactions_summary, meId);
                    wrapper.innerHTML = reactionsHtml;
                    reactions.initMessageReactions(messageElement, messageId, meId);
                    console.log('[chat-detail-enhanced] ✓ Reactions updated successfully');
                } else {
                    console.warn('[chat-detail-enhanced] ✗ Wrapper not found in message');
                }
            });
        } else {
            if (!data.reactions_summary) {
                console.warn('[chat-detail-enhanced] ✗ No reactions_summary in WebSocket data');
            }
            if (!messageElements.length) {
                console.warn('[chat-detail-enhanced] ✗ Message element not found for ID:', messageId);
            }
        }
    });
    
    // ==================== ИНИЦИАЛИЗАЦИЯ КОНТЕКСТНОГО МЕНЮ ====================
    
    // Инициализируем контекстное меню с динамическими эмодзи из БД
    const contextMenu = new MessageContextMenu({
        currentUserId: meId,
        emojis: availableEmojis,  // Используем загруженные из БД
        onReactionSelect: async (messageId, emoji) => {
            await reactions.addReaction(messageId, emoji);
        }
    });

    // ==================== Глобальные функции для совместимости ====================
    
    // Эти функции нужны для работы со старым HTML (inline onclick)
    window.addReaction = function(messageId, emoji) {
        reactions.addReaction(messageId, emoji);
    };

    window.toggleReaction = function(messageId, emoji) {
        const msgEl = document.querySelector(`[data-message-id="${messageId}"]`);
        const reactionBtn = msgEl?.querySelector(`.reaction-item[data-emoji="${emoji}"]`);
        
        if (reactionBtn?.classList.contains('active')) {
            reactions.removeReaction(messageId, emoji);
        } else {
            reactions.addReaction(messageId, emoji);
        }
    };
    
    // ==================== Инициализация существующих сообщений ====================

    // Инициализация реакций для существующих сообщений
    function initMessageReactions() {
        const messages = document.querySelectorAll('[data-message-id]');
        messages.forEach(messageElement => {
            const messageId = messageElement.dataset.messageId;
            const wrapper = messageElement.querySelector('.message-reactions-wrapper');
            if (wrapper && !wrapper.querySelector('.message-reactions')) {
                // Загрузить существующие реакции из data-атрибута
                let existingReactions = {};
                try {
                    const reactionsJson = messageElement.dataset.reactions;
                    if (reactionsJson && reactionsJson !== '{}') {
                        existingReactions = JSON.parse(reactionsJson);
                    }
                } catch (e) {
                    console.error('Error parsing reactions:', e);
                }
                
                // Отрендерить контейнер реакций с существующими реакциями
                const reactionsHtml = reactions.renderReactions(existingReactions, meId);
                wrapper.innerHTML = reactionsHtml;
                // Инициализировать обработчики
                reactions.initMessageReactions(messageElement, messageId, meId);
            }
            
            // Подключить контекстное меню к сообщению
            if (!messageElement.dataset.contextMenuAttached) {
                contextMenu.attachToMessage(messageElement);
                messageElement.dataset.contextMenuAttached = 'true';
                messageElement.classList.add('message-context-menu-enabled');
            }
        });
    }

    // Наблюдатель за новыми сообщениями
    const messageObserver = new MutationObserver((mutations) => {
        mutations.forEach((mutation) => {
            mutation.addedNodes.forEach((node) => {
                if (node.nodeType === 1 && node.dataset && node.dataset.messageId) {
                    const wrapper = node.querySelector('.message-reactions-wrapper');
                    if (wrapper && !wrapper.querySelector('.message-reactions')) {
                        // Читаем существующие реакции из data-атрибута
                        let existingReactions = {};
                        try {
                            const reactionsJson = node.dataset.reactions;
                            if (reactionsJson && reactionsJson !== '{}') {
                                existingReactions = JSON.parse(reactionsJson);
                            }
                        } catch (e) {
                            console.error('Error parsing reactions for new message:', e);
                        }
                        
                        const reactionsHtml = reactions.renderReactions(existingReactions, meId);
                        wrapper.innerHTML = reactionsHtml;
                        reactions.initMessageReactions(node, node.dataset.messageId, meId);
                    }
                    
                    // Подключить контекстное меню к новому сообщению
                    if (!node.dataset.contextMenuAttached) {
                        contextMenu.attachToMessage(node);
                        node.dataset.contextMenuAttached = 'true';
                        node.classList.add('message-context-menu-enabled');
                    }
                }
            });
        });
    });
    
    messageObserver.observe(chatScroll, {
        childList: true,
        subtree: true
    });

    // ==================== Init ====================
    
    initMessageReactions();
    
    // Обработка обновлений голосований через WebSocket
    window.addEventListener('chat:poll-update', (event) => {
        const { poll_id } = event.detail;
        if (window.chatPoll) {
            // Всегда делаем refreshPoll для получения персонализированных данных
            // (user_voted_option_ids не передаётся через WebSocket, т.к. это общий канал)
            console.log('[chat-detail-enhanced] Poll update received, refreshing poll_id=%s', poll_id);
            window.chatPoll.refreshPoll(poll_id);
        }
    });
    
    // Scroll button
    const scrollBtn = document.getElementById('scrollBtn');
    scrollBtn?.addEventListener('click', () => {
        chatScroll.scrollTop = chatScroll.scrollHeight;
    });
}

// Запускаем инициализацию
initChatDetail().catch(error => {
    console.error('[chat-detail-enhanced] Initialization failed:', error);
});

} // end if (__CHAT_DETAIL_ENHANCED_INITIALIZED__)
