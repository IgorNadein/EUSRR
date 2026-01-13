/**
 * @fileoverview Chat Detail Page - инициализация страницы детального просмотра чата
 * @module pages/chatDetail
 * 
 * НОВАЯ АРХИТЕКТУРА (v2.0):
 * Использует единый ChatController для управления всеми аспектами чата:
 * - MessageStore - централизованное хранилище
 * - MessageLoader - загрузка и обновления
 * - MessageRendererV2 - чистый рендеринг
 * - ScrollManager - умная прокрутка
 * 
 * Старые компоненты (Composer, FormManager, MarkRead) остаются для дополнительной функциональности
 */

// Асинхронная загрузка модулей
(async function() {
  let initChatMarkRead, initChatComposer, initChatFormManager, ChatController;

  try {
    console.log('[ChatDetail] Loading modules...');
    const modules = await Promise.all([
      import('../components/chatMarkRead.js'),
      import('../components/chatComposer.js'),
      import('../components/chatFormManager.js'),
      import('../chat/index.js')  // ✅ V2 автоматически (ChatController = ChatControllerV2)
    ]);
    
    console.log('[ChatDetail] Modules loaded:', modules.map(m => Object.keys(m)));
    
    initChatMarkRead = modules[0].initChatMarkRead;
    initChatComposer = modules[1].initChatComposer;
    initChatFormManager = modules[2].initChatFormManager;
    ChatController = modules[3].ChatController;
    
    console.log('[ChatDetail] ChatController:', ChatController);
    
    if (!ChatController) {
      throw new Error('ChatController is undefined - check export in chatController.js');
    }
  } catch (error) {
    console.error('[ChatDetail] Failed to load modules:', error);
    alert('Ошибка загрузки модулей чата: ' + error.message);
    return; // Прекращаем выполнение
  }

/**
 * Инициализация при готовности DOM
 * Читает конфигурацию из data-атрибутов и запускает инициализацию компонентов
 */
function initWhenReady() {
  // Получаем данные из data-атрибутов
  const appContainer = document.getElementById('chatDetailApp');
  
  if (!appContainer) {
    console.warn('[ChatDetail] App container not found');
    return;
  }
  
  // Читаем конфигурацию из data-атрибутов
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
    // Правильная обработка 0: проверяем наличие атрибута, а не значение
    lastReadMessageId: appContainer.dataset.lastReadMessageId ? Number(appContainer.dataset.lastReadMessageId) : null
  };
  
  console.log('[ChatDetail] 🔍 lastReadMessageId from HTML:', {
    rawValue: appContainer.dataset.lastReadMessageId,
    parsedValue: config.lastReadMessageId,
    type: typeof config.lastReadMessageId
  });
  
  // Читаем дополнительные URL из chatScroll (для рендеринга сообщений)
  const chatScroll = document.getElementById('chatScroll');
  if (chatScroll) {
    config.profileUrl = chatScroll.dataset.profileUrl;
    config.detailUrlTemplate = chatScroll.dataset.detailUrlTemplate;
  }
  
  console.log('[ChatDetail] Config:', config);
  
  if (!config.chatId) {
    console.error('[ChatDetail] chatId is required');
    return;
  }
  
  // Ждём инициализации WebSocket
  waitForWebSocket().then((userWs) => {
    console.log('[ChatDetail] WebSocket ready, initializing components');
    initializeComponents(config, userWs);
  }).catch((error) => {
    console.error('[ChatDetail] WebSocket initialization failed:', error);
  });
}

// Запускаем инициализацию
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initWhenReady);
} else {
  // DOM уже готов
  initWhenReady();
}

/**
 * Ожидание готовности WebSocket соединения
 * @returns {Promise<Object>} Промис с API WebSocket
 * @throws {Error} Если WebSocket не инициализирован за 10 секунд
 */
function waitForWebSocket() {
  return new Promise((resolve, reject) => {
    // Если уже готов - используем сразу
    if (window.userWebSocket && window.userWebSocket.ws) {
      console.log('[ChatDetail] WebSocket already available');
      resolve(window.userWebSocket);
      return;
    }
    
    // Ждём события с таймаутом
    console.log('[ChatDetail] Waiting for user:ws-ready event...');
    let timeoutId;
    
    const handler = (e) => {
      console.log('[ChatDetail] user:ws-ready event received');
      clearTimeout(timeoutId);
      resolve(e.detail.api);
    };
    
    window.addEventListener('user:ws-ready', handler, { once: true });
    
    timeoutId = setTimeout(() => {
      window.removeEventListener('user:ws-ready', handler);
      reject(new Error('WebSocket initialization timeout'));
    }, 10000); // 10 секунд
  });
}

/**
 * Инициализация всех компонентов страницы чата
 * @param {Object} config - Конфигурация из data-атрибутов
 * @param {number} config.chatId - ID чата
 * @param {number} config.userId - ID текущего пользователя
 * @param {string} config.userName - Имя текущего пользователя
 * @param {string} config.userAvatar - URL аватара пользователя
 * @param {string} config.uploadUrl - URL для загрузки файлов
 * @param {string} config.messagesUrl - URL для загрузки истории
 * @param {string} config.markReadUrl - URL для отметки прочтения
 * @param {Object} userWs - API WebSocket соединения
 */
async function initializeComponents(config, userWs) {
  console.log('[ChatDetail] 🚀 Initializing with NEW ChatController architecture...');
  
  const scrollElement = document.getElementById('chatScroll');
  if (!scrollElement) {
    console.error('[ChatDetail] Scroll container not found');
    return;
  }

  // ========== 0. ОТКРЫВАЕМ ЧАТ В WEBSOCKET (ДО ChatController) ==========
  // ВАЖНО: Открываем ДО инициализации чтобы избежать late initial_messages
  // loadHistory=false - не загружаем через WS, ChatController загрузит через HTTP
  if (userWs && userWs.openChat) {
    userWs.openChat(config.chatId, false);
    console.log('[ChatDetail] ✅ Chat opened in WebSocket (before init)');
  }
  
  // ========== 1. CHAT CONTROLLER (НОВАЯ АРХИТЕКТУРА) ==========
  // Один контроллер заменяет: MessageRenderer, MessageLoader, ScrollManager, HistoryLoader
  console.log('[ChatDetail] Creating ChatController...');
  
  const chatController = new ChatController({
    chatId: config.chatId,
    currentUserId: config.userId,
    scrollElement: scrollElement,
    containerId: 'chatScroll',
    wsConnection: userWs,
    profileUrl: config.profileUrl || '/employees/profile/',
    detailUrlTemplate: config.detailUrlTemplate || '/employees/detail/0/',
    messagesUrl: config.messagesUrl,
    lastReadMessageId: config.lastReadMessageId,  // ✅ Передаем message_id
    lastReadTimestamp: config.lastReadTimestamp   // ✅ Fallback на timestamp
  });
  
  console.log('[ChatDetail] Initializing ChatController...');
  await chatController.init();
  console.log('[ChatDetail] ✅ ChatController initialized');
  
  // ========== 2. FORM MANAGER ==========
  // Управление формой редактирования сообщений
  const formManager = initChatFormManager({
    formId: 'chatForm',
    textareaId: 'id_content',
    chatId: config.chatId,
    uploadUrl: config.uploadUrl,
    editUrlTemplate: config.editUrlTemplate
  });
  
  if (!formManager) {
    console.error('[ChatDetail] FormManager initialization failed');
    return;
  }
  console.log('[ChatDetail] ✅ FormManager initialized');
  
  // ========== 3. MARK READ API ==========
  // Отслеживание прочитанных сообщений
  const markReadApi = initChatMarkRead({
    chatId: config.chatId,
    meId: config.userId,
    scrollContainerId: 'chatScroll',
    textareaId: 'id_content',
    formId: 'chatForm',
    scrollBtnId: 'scrollBtn',
    markReadUrl: config.markReadUrl,
    initialLastReadTs: config.lastReadTimestamp
  });
  console.log('[ChatDetail] ✅ MarkRead initialized');
  
  // ========== 4. COMPOSER ==========
  // Отправка новых сообщений (использует ChatController для добавления)
  const composer = initChatComposer({
    chatId: config.chatId,
    formId: 'chatForm',
    textareaId: 'id_content',
    uploadUrl: config.uploadUrl,
    meId: config.userId,
    meName: config.userName,
    meAvatar: config.userAvatar,
    chatController: chatController  // НОВОЕ: передаем контроллер вместо renderer
  });
  
  if (!composer) {
    console.error('[ChatDetail] Composer initialization failed');
    return;
  }
  console.log('[ChatDetail] ✅ Composer initialized');
  
  // ========== 5. EXPORT TO WINDOW ==========
  // Для доступа из других скриптов и отладки
  window.chatController = chatController;
  window.chatComposer = composer;
  window.markReadApi = markReadApi;
  window.chatFormManager = formManager;
  
  // DEPRECATED: Старые API для backward compatibility
  window.messageRenderer = {
    renderMessage: (msg) => console.warn('[DEPRECATED] Use chatController instead'),
    renderMessages: (msgs) => console.warn('[DEPRECATED] Use chatController instead')
  };
  window.chatHistoryLoader = {
    loadMore: () => chatController.loadMoreHistory()
  };
  
  console.log('[ChatDetail] ✅ All components initialized successfully');
  console.log('[ChatDetail] 📊 Available APIs: window.chatController, window.chatComposer, window.markReadApi');
  
  // Контекстное меню и выделение сообщений инициализируются в chat-detail-enhanced.js
}

})(); // Закрываем async IIFE