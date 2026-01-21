/**
 * Enhanced Chat Detail - только UI компоненты (реакции, контекстное меню, выделение, голосования)
 * WebSocket управление вынесено в chatWebSocket.js (base.html)
 */
import MessageReactions from './components/messageReactions.js';
import MessageContextMenu from './components/messageContextMenu.js';
import MessageSelection from './components/messageSelection.js';
import ChatPoll from './components/chatPoll.js';
import { initMessageEditing } from './components/messageEditing.js';
import { initChatFormManager } from './components/chatFormManager.js';
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
        const allEmojis = reactionsConfig.getEmojis();
        // Берем только первые 5 эмодзи для быстрых реакций
        const availableEmojis = allEmojis.slice(0, 5);
        console.log('[chat-detail-enhanced] ✓ Available emojis (quick):', availableEmojis);
        console.log('[chat-detail-enhanced] ✓ All emojis:', allEmojis);

        // Инициализируем систему реакций
        const reactions = new MessageReactions();
        console.log('[chat-detail-enhanced] MessageReactions initialized');

        // Делаем доступным глобально
        window.reactions = reactions;

        // Инициализируем обработку редактирования сообщений
        initMessageEditing();
        console.log('[chat-detail-enhanced] Message editing initialized');

        // Инициализируем менеджер формы (для редактирования/ответов)
        const formManager = initChatFormManager({
            chatId: chatId,
            formId: 'chatForm',
            textareaId: 'id_content'
        });

        if (formManager) {
            console.log('[chat-detail-enhanced] ChatFormManager initialized');
        } else {
            console.warn('[chat-detail-enhanced] ChatFormManager init failed - form elements not found');
        }

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

// Делаем доступным глобально для использования в других модулей
    window.chatPoll = chatPoll;
    
    // ==================== ОБРАБОТЧИК КЛИКОВ ПО ПРЕВЬЮ ОТВЕТОВ ====================
    
    /**
     * Делегированный обработчик для всех .message-reply-preview
     * Работает как для серверных, так и для динамических сообщений
     */
    chatScroll.addEventListener('click', (e) => {
        const replyPreview = e.target.closest('.message-reply-preview');
        if (!replyPreview) return;
        
        const replyToId = replyPreview.dataset.replyToId;
        if (!replyToId) return;
        
        e.preventDefault();
        e.stopPropagation();
        
        // Ищем целевое сообщение
        const targetMsg = document.querySelector(`[data-message-id="${replyToId}"]`);
        if (!targetMsg) return;
        
        // Скроллим к сообщению
        targetMsg.scrollIntoView({ behavior: 'smooth', block: 'center' });
        
        // Добавляем анимацию подсветки к .msg
        targetMsg.classList.remove('highlight-flash');
        setTimeout(() => {
            targetMsg.classList.add('highlight-flash');
            setTimeout(() => targetMsg.classList.remove('highlight-flash'), 1500);
        }, 10);
    });

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
                    // Используем централизованный MessageReactions для обновления
                    reactions.updateMessageReactions(messageElement, data.reactions_summary, meId);
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
        // Обработка удаления реакции через WebSocket
        window.addEventListener('chat:reaction-removed', (event) => {
            console.log('[chat-detail-enhanced] WebSocket: reaction-removed', event.detail);
            const data = event.detail;
            const messageId = data.message_id || data.messageId;

            console.log('[chat-detail-enhanced] Looking for message ID:', messageId);
            console.log('[chat-detail-enhanced] Reactions summary:', data.reactions_summary);

            const messageElements = document.querySelectorAll(`[data-message-id="${messageId}"]`);
            console.log('[chat-detail-enhanced] Found message elements:', messageElements.length);

            if (messageElements.length && data.reactions_summary !== undefined) {
                messageElements.forEach(messageElement => {
                    // Используем централизованный MessageReactions для обновления
                    reactions.updateMessageReactions(messageElement, data.reactions_summary, meId);
                });
            } else {
                if (data.reactions_summary === undefined) {
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
        window.addReaction = function (messageId, emoji) {
            reactions.addReaction(messageId, emoji);
        };

        window.toggleReaction = function (messageId, emoji) {
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
            console.log('[chat-detail-enhanced] Initializing reactions for', messages.length, 'messages');

            messages.forEach(messageElement => {
                const messageId = messageElement.dataset.messageId;

                // Инициализировать обработчики реакций если есть контейнер
                const reactionsContainer = messageElement.querySelector('.message-reactions');
                if (reactionsContainer) {
                    console.log('[chat-detail-enhanced] Initializing reactions handlers for message:', messageId);
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
                        console.log('[chat-detail-enhanced] New message detected:', node.dataset.messageId);

                        // Инициализировать обработчики реакций если есть контейнер
                        const reactionsContainer = node.querySelector('.message-reactions');
                        if (reactionsContainer) {
                            console.log('[chat-detail-enhanced] Initializing reactions handlers for new message');
                            reactions.initMessageReactions(node, node.dataset.messageId, meId);
                        }

                        // Подключить контекстное меню
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

        // Делегированный обработчик кликов на реакции - используем MessageReactions
        document.addEventListener('click', async (e) => {
            const reactionBtn = e.target.closest('.reaction-button');
            if (reactionBtn && !reactionBtn.classList.contains('add-reaction')) {
                e.preventDefault();

                const messageEl = reactionBtn.closest('[data-message-id]');
                if (!messageEl) return;

                const messageId = messageEl.dataset.messageId;
                const emoji = reactionBtn.dataset.emoji;
                const isActive = reactionBtn.classList.contains('active');

                try {
                    if (isActive) {
                        await reactions.removeReaction(messageId);
                    } else {
                        await reactions.addReaction(messageId, emoji);
                    }
                } catch (error) {
                    console.error('[chat-detail-enhanced] Reaction error:', error);
                }
            }
        });

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
    }

    // Запускаем инициализацию
    initChatDetail().catch(error => {
        console.error('[chat-detail-enhanced] Initialization failed:', error);
    });

} // end if (__CHAT_DETAIL_ENHANCED_INITIALIZED__)
