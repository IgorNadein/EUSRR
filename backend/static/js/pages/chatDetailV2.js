/**
 * @fileoverview Chat Detail Page V2 - рефакторированная инициализация чата
 * @module pages/chatDetailV2
 * 
 * НОВАЯ АРХИТЕКТУРА V2:
 * - Использует ChatControllerV2 с чистой архитектурой
 * - MessageStoreV2 с бинарным поиском
 * - MessageLoaderV2 с retry-логикой
 * - ScrollManagerV2 с debounce/throttle
 * - Минимум логирования
 */

(async function() {
    'use strict';

    // ==================== Загрузка модулей ====================
    
    let ChatControllerV2, initChatMarkRead, initChatComposer, initChatFormManager;

    try {
        const [
            controllerModule,
            markReadModule,
            composerModule,
            formManagerModule
        ] = await Promise.all([
            import('../controllers/chatControllerV2.js'),
            import('../components/chatMarkRead.js'),
            import('../components/chatComposer.js'),
            import('../components/chatFormManager.js')
        ]);

        ChatControllerV2 = controllerModule.ChatControllerV2;
        initChatMarkRead = markReadModule.initChatMarkRead;
        initChatComposer = composerModule.initChatComposer;
        initChatFormManager = formManagerModule.initChatFormManager;

        if (!ChatControllerV2) {
            throw new Error('ChatControllerV2 is undefined');
        }
    } catch (error) {
        console.error('[ChatDetailV2] Failed to load modules:', error);
        return;
    }

    // ==================== Конфигурация ====================

    /**
     * Читает конфигурацию из DOM
     * @returns {Object|null}
     */
    function readConfig() {
        const appContainer = document.getElementById('chatDetailApp');
        if (!appContainer) {
            console.warn('[ChatDetailV2] App container not found');
            return null;
        }

        const scrollContainer = document.getElementById('chatScroll');
        
        const config = {
            chatId: Number(appContainer.dataset.chatId),
            userId: Number(appContainer.dataset.userId),
            userName: appContainer.dataset.userName || 'Вы',
            userAvatar: appContainer.dataset.userAvatar || '',
            uploadUrl: appContainer.dataset.uploadUrl,
            messagesUrl: appContainer.dataset.messagesUrl,
            markReadUrl: appContainer.dataset.markReadUrl,
            editUrlTemplate: appContainer.dataset.editUrlTemplate,
            lastReadTimestamp: Number(appContainer.dataset.lastReadTimestamp) || null,
            lastReadMessageId: appContainer.dataset.lastReadMessageId 
                ? Number(appContainer.dataset.lastReadMessageId) 
                : null,
            profileUrl: scrollContainer?.dataset.profileUrl || '/employees/profile/',
            detailUrlTemplate: scrollContainer?.dataset.detailUrlTemplate || '/employees/detail/0/'
        };
        
        console.log('[ChatDetailV2] 🔍 Config:', {
            lastReadMessageId: config.lastReadMessageId,
            lastReadTimestamp: config.lastReadTimestamp,
            rawMessageId: appContainer.dataset.lastReadMessageId,
            rawTimestamp: appContainer.dataset.lastReadTimestamp
        });
        
        return config;
    }

    /**
     * Ждет готовности WebSocket
     * @param {number} timeout - Таймаут в мс
     * @returns {Promise<Object>}
     */
    function waitForWebSocket(timeout = 10000) {
        return new Promise((resolve, reject) => {
            // Уже готов
            if (window.userWebSocket?.ws) {
                resolve(window.userWebSocket);
                return;
            }

            let timeoutId;
            
            const handler = (e) => {
                clearTimeout(timeoutId);
                resolve(e.detail.api);
            };

            window.addEventListener('user:ws-ready', handler, { once: true });

            timeoutId = setTimeout(() => {
                window.removeEventListener('user:ws-ready', handler);
                reject(new Error('WebSocket connection timeout'));
            }, timeout);
        });
    }

    // ==================== Инициализация компонентов ====================

    /**
     * Инициализирует все компоненты чата
     * @param {Object} config - Конфигурация
     * @param {Object} wsApi - WebSocket API
     */
    async function initializeComponents(config, wsApi) {
        const scrollElement = document.getElementById('chatScroll');
        if (!scrollElement) {
            console.error('[ChatDetailV2] Scroll container not found');
            return;
        }

        // 0. Открываем чат в WebSocket ДО инициализации
        if (wsApi?.openChat) {
            wsApi.openChat(config.chatId, false);
        }

        // 1. Chat Controller (главный координатор)
        const chatController = new ChatControllerV2({
            chatId: config.chatId,
            currentUserId: config.userId,
            scrollElement,
            containerId: 'chatScroll',
            wsConnection: wsApi,
            profileUrl: config.profileUrl,
            detailUrlTemplate: config.detailUrlTemplate,
            lastReadMessageId: config.lastReadMessageId,
            lastReadTimestamp: config.lastReadTimestamp  // ✅ Fallback для скролла
        });

        await chatController.init();
        console.log('[ChatDetailV2] ChatController initialized');

        // 2. Form Manager (редактирование сообщений)
        const formManager = initChatFormManager({
            formId: 'chatForm',
            textareaId: 'id_content',
            chatId: config.chatId,
            uploadUrl: config.uploadUrl,
            editUrlTemplate: config.editUrlTemplate
        });

        // 3. Mark Read (отслеживание прочитанных)
        const markReadApi = initChatMarkRead({
            chatId: config.chatId,
            meId: config.userId,
            scrollContainerId: 'chatScroll',
            textareaId: 'id_content',
            formId: 'chatForm',
            scrollBtnId: 'scrollBtn',
            markReadUrl: config.markReadUrl,
            initialLastReadTs: config.lastReadMessageId
        });

        // 4. Composer (отправка сообщений)
        const composer = initChatComposer({
            chatId: config.chatId,
            formId: 'chatForm',
            textareaId: 'id_content',
            uploadUrl: config.uploadUrl,
            meId: config.userId,
            meName: config.userName,
            meAvatar: config.userAvatar,
            chatController
        });

        // 5. Экспорт в window
        window.chatController = chatController;
        window.chatComposer = composer;
        window.markReadApi = markReadApi;
        window.chatFormManager = formManager;

        // Backward compatibility
        window.messageRenderer = {
            renderMessage: () => console.warn('[DEPRECATED] Use chatController'),
            renderMessages: () => console.warn('[DEPRECATED] Use chatController')
        };
        window.chatHistoryLoader = {
            loadMore: () => chatController.loadMoreHistory()
        };

        console.log('[ChatDetailV2] All components initialized');
    }

    // ==================== Entry Point ====================

    /**
     * Главная функция инициализации
     */
    async function init() {
        console.log('[ChatDetailV2] 🚀🚀🚀 INIT STARTED - V2 FILE LOADED 🚀🚀🚀');
        const config = readConfig();
        console.log('[ChatDetailV2] 🔍 Config read result:', config);
        if (!config || !config.chatId) {
            console.error('[ChatDetailV2] Invalid configuration');
            return;
        }

        try {
            const wsApi = await waitForWebSocket();
            await initializeComponents(config, wsApi);
        } catch (error) {
            console.error('[ChatDetailV2] Initialization failed:', error);
            
            // Показываем ошибку пользователю
            const scrollEl = document.getElementById('chatScroll');
            if (scrollEl) {
                scrollEl.innerHTML = `
                    <div class="alert alert-danger m-3">
                        <i class="bi bi-exclamation-triangle me-2"></i>
                        Ошибка загрузки чата. 
                        <a href="#" onclick="location.reload()">Обновить страницу</a>
                    </div>
                `;
            }
        }
    }

    // Запуск
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

})();
