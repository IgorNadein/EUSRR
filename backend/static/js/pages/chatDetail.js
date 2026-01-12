/**
 * Chat Detail Page
 * Инициализация страницы детального просмотра чата
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

// Ждём DOM
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
 * Ожидание готовности WebSocket
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
 * Инициализация всех компонентов страницы
 */
function initializeComponents(config, userWs) {
  // ========== FORM MANAGER ==========
  console.log('[ChatDetail] Initializing FormManager...');
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
  
  console.log('[ChatDetail] FormManager initialized');
  
  // ========== MARK READ ==========
  console.log('[ChatDetail] Initializing MarkRead...');
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
  
  console.log('[ChatDetail] MarkRead initialized');
  
  // ========== COMPOSER ==========
  console.log('[ChatDetail] Initializing Composer...');
  const composer = initChatComposer({
    chatId: config.chatId,
    formId: 'chatForm',
    textareaId: 'id_content',
    uploadUrl: config.uploadUrl,
    meId: config.userId,
    meName: config.userName,
    meAvatar: config.userAvatar
  });
  
  if (!composer) {
    console.error('[ChatDetail] Composer initialization failed');
    return;
  }
  
  console.log('[ChatDetail] Composer initialized:', composer);
  
  // ========== HISTORY LOADER ==========
  console.log('[ChatDetail] Initializing HistoryLoader...');
  
  // Получаем avatarMap если доступен
  const avatarMap = window.chatAvatarMap?.getAll() || {};
  
  const historyLoader = initChatHistoryLoader({
    chatId: config.chatId,
    scrollContainerId: 'chatScroll',
    fetchUrl: config.messagesUrl,
    avatarMap: avatarMap,
    meId: config.userId
  });
  
  console.log('[ChatDetail] HistoryLoader initialized');
  
  // ========== MESSAGE RENDERER ==========
  console.log('[ChatDetail] Initializing MessageRenderer...');
  
  const messageRenderer = new MessageRenderer({
    containerId: 'chatScroll',
    currentUserId: config.userId,
    currentUserAvatar: config.userAvatar || '',
    profileUrl: config.profileUrl || '/employees/profile/',
    detailUrlTemplate: config.detailUrlTemplate || '/employees/detail/0/'
  });
  
  console.log('[ChatDetail] MessageRenderer initialized');
  
  // ========== CONTEXT MENU ==========
  // Инициализация контекстного меню перенесена в chat-detail-enhanced.js
  // для избежания конфликтов и дублирования
  
  // ========== CONFIGURE WEBSOCKET ==========
  console.log('[ChatDetail] Configuring WebSocket...');
  
  if (userWs && userWs.configure) {
    userWs.configure({
      scrollContainerId: 'chatScroll',
      formId: 'chatForm',
      textareaId: 'id_content',
      typingIndicatorId: 'typing',
      avatarMap: avatarMap,
      markReadApi: markReadApi,
      messageRenderer: messageRenderer  // Добавляем MessageRenderer
    });
  }
  
  // Открываем чат в WebSocket с загрузкой истории
  if (userWs && userWs.openChat) {
    console.log('[ChatDetail] Opening chat in WebSocket with history:', config.chatId);
    userWs.openChat(config.chatId, true);  // true = загружаем initial_messages
  }
  
  // ========== EXPORT APIS ==========
  window.chatComposer = composer;
  window.chatHistoryLoader = historyLoader;
  window.markReadApi = markReadApi;
  window.chatFormManager = formManager;
  
  // Контекстное меню и выделение сообщений инициализируются в chat-detail-enhanced.js
  
  console.log('[ChatDetail] All components initialized successfully ✓');
}