/**
 * @fileoverview Chat Detail Page - инициализация страницы детального просмотра чата
 * @module pages/chatDetail
 * 
 * Порядок инициализации компонентов:
 * 1. MessageRenderer - единый источник рендеринга сообщений
 * 2. FormManager - управление формой редактирования
 * 3. MarkRead API - отслеживание прочитанных сообщений
 * 4. Composer - отправка новых сообщений и файлов
 * 5. HistoryLoader - подгрузка старых сообщений при скролле
 * 6. WebSocket - real-time сообщения и события
 * 
 * РЕФАКТОРИНГ: Унифицированная архитектура загрузки сообщений
 * - Все компоненты используют единый MessageRenderer
 * - WebSocket для initial messages
 * - HTTP для истории (pagination)
 * - Composer для pending messages
 */

let initChatMarkRead, initChatComposer, initChatHistoryLoader, initChatFormManager, MessageRenderer;

try {
  const modules = await Promise.all([
    import('../components/chatMarkRead.js'),
    import('../components/chatComposer.js'),
    import('../components/chatHistoryLoader.js'),
    import('../components/chatFormManager.js'),
    import('../components/messageRenderer.js')
  ]);
  
  initChatMarkRead = modules[0].initChatMarkRead;
  initChatComposer = modules[1].initChatComposer;
  initChatHistoryLoader = modules[2].initChatHistoryLoader;
  initChatFormManager = modules[3].initChatFormManager;
  MessageRenderer = modules[4].MessageRenderer;
} catch (error) {
  console.error('[ChatDetail] Failed to load modules:', error);
  alert('Ошибка загрузки модулей чата: ' + error.message);
  throw error;
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
    lastReadTimestamp: Number(appContainer.dataset.lastReadTimestamp) || null
  };
  
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
function initializeComponents(config, userWs) {
  console.log('[ChatDetail] Initializing components...');
  
  // Получаем avatarMap если доступен
  const avatarMap = window.chatAvatarMap?.getAll() || {};
  
  // ========== 1. MESSAGE RENDERER ==========
  // Создается первым, т.к. используется другими компонентами
  const messageRenderer = new MessageRenderer({
    containerId: 'chatScroll',
    currentUserId: config.userId,
    currentUserAvatar: config.userAvatar || '',
    profileUrl: config.profileUrl || '/employees/profile/',
    detailUrlTemplate: config.detailUrlTemplate || '/employees/detail/0/'
  });
  console.log('[ChatDetail] ✓ MessageRenderer initialized');
  
  // ========== 2. FORM MANAGER ==========
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
  console.log('[ChatDetail] ✓ FormManager initialized');
  
  // ========== 3. MARK READ API ==========
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
  console.log('[ChatDetail] ✓ MarkRead initialized');
  
  // ========== 4. COMPOSER ==========
  const composer = initChatComposer({
    chatId: config.chatId,
    formId: 'chatForm',
    textareaId: 'id_content',
    uploadUrl: config.uploadUrl,
    meId: config.userId,
    meName: config.userName,
    meAvatar: config.userAvatar,
    messageRenderer: messageRenderer
  });
  
  if (!composer) {
    console.error('[ChatDetail] Composer initialization failed');
    return;
  }
  console.log('[ChatDetail] ✓ Composer initialized');
  
  // ========== 5. HISTORY LOADER ==========
  const historyLoader = initChatHistoryLoader({
    chatId: config.chatId,
    scrollContainerId: 'chatScroll',
    fetchUrl: config.messagesUrl,
    avatarMap: avatarMap,
    meId: config.userId,
    messageRenderer: messageRenderer
  });
  console.log('[ChatDetail] ✓ HistoryLoader initialized');
  
  // ========== 6. CONFIGURE WEBSOCKET ==========
  if (userWs && userWs.configure) {
    userWs.configure({
      scrollContainerId: 'chatScroll',
      formId: 'chatForm',
      textareaId: 'id_content',
      typingIndicatorId: 'typing',
      avatarMap: avatarMap,
      markReadApi: markReadApi,
      messageRenderer: messageRenderer
    });
    console.log('[ChatDetail] ✓ WebSocket configured');
  }
  
  // ========== 7. OPEN CHAT IN WEBSOCKET ==========
  // Загружаем начальные сообщения через WebSocket
  if (userWs && userWs.openChat) {
    userWs.openChat(config.chatId, true);  // true = загружаем initial_messages
    console.log('[ChatDetail] ✓ Chat opened in WebSocket');
  }
  
  // ========== 8. EXPORT APIS TO WINDOW ==========
  // Для доступа из других скриптов и отладки
  window.chatComposer = composer;
  window.chatHistoryLoader = historyLoader;
  window.markReadApi = markReadApi;
  window.chatFormManager = formManager;
  window.messageRenderer = messageRenderer;
  
  console.log('[ChatDetail] ✅ All components initialized successfully');
  
  // Контекстное меню и выделение сообщений инициализируются в chat-detail-enhanced.js
  
  console.log('[ChatDetail] All components initialized successfully ✓');
}