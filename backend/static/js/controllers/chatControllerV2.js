/**
 * @fileoverview ChatController V2 - рефакторированный координатор чата
 * @module controllers/chatControllerV2
 *
 * РЕФАКТОРИНГ:
 * - Чистая архитектура с разделением ответственности
 * - Минимум логирования (только важные события)
 * - Улучшенная обработка ошибок
 * - Полная типизация JSDoc
 * - Поддержка отмены операций
 */

import { MessageStoreV2 } from "../stores/messageStoreV2.js";
import { MessageLoaderV2 } from "../loaders/messageLoaderV2.js";
import { MessageRendererV2 } from "../renderers/messageRendererV2.js";
import { ScrollManagerV2 } from "../managers/scrollManagerV2.js";
import { DateGroupManager } from "../managers/dateGroupManager.js";
import { StickyDateObserver } from "../observers/stickyDateObserver.js";
import { UnreadBadgeManager } from "../managers/unreadBadgeManager.js";
import {
  CHAT_EVENTS,
  WS_EVENTS,
  SCROLL_CONFIG,
  AUTOSCROLL_CONFIG,
} from "../config/chatConfig.js";

/**
 * @typedef {Object} ChatControllerOptions
 * @property {number} chatId - ID чата
 * @property {HTMLElement} scrollElement - Контейнер для скролла
 * @property {number} currentUserId - ID текущего пользователя
 * @property {string} [containerId='chatScroll'] - ID контейнера сообщений
 * @property {Object} [wsConnection] - WebSocket соединение
 * @property {string} [profileUrl] - URL профиля пользователя
 * @property {string} [detailUrlTemplate] - Шаблон URL детальной информации
 * @property {number|null} [lastReadMessageId] - ID последнего прочитанного сообщения
 */

/**
 * ChatController V2 - главный координатор чата
 * Единая точка входа для работы с чатом.
 */
export class ChatControllerV2 {
  /**
   * @param {ChatControllerOptions} options
   */
  constructor(options) {
    this._validateOptions(options);

    // Основные параметры
    this.chatId = options.chatId;
    this.currentUserId = options.currentUserId;
    this.scrollElement = options.scrollElement;
    this.containerId = options.containerId || "chatScroll";
    this.lastReadMessageId = options.lastReadMessageId || null;
    this.lastReadTimestamp = options.lastReadTimestamp || null;
    
    // Для корректировки скролла при загрузке изображений
    this._anchorElement = null;
    this._anchorOffsetTop = 0;
    this._lastScrollHeight = 0;
    this._imageLoadHandlers = [];

    // Создаем компоненты
    this.store = new MessageStoreV2({ currentUserId: this.currentUserId });

    // Date Group Manager для группировки по датам
    this.dateGroupManager = new DateGroupManager({
      container: this.scrollElement,
      enableSticky: true,
      interactive: true, // Кликабельные даты
    });

    // Sticky Date Observer для IntersectionObserver
    this.stickyDateObserver = new StickyDateObserver({
      container: this.scrollElement,
      onSticky: (isSticky, element, dateText) => {
        console.log("[ChatControllerV2] Date sticky state:", {
          dateText,
          isSticky,
        });
      },
    });

    this.loader = new MessageLoaderV2({
      store: this.store,
      wsConnection: options.wsConnection,
      currentUserId: this.currentUserId,
    });

    this.renderer = new MessageRendererV2({
      store: this.store,
      containerId: this.containerId,
      currentUserId: this.currentUserId,
      dateGroupManager: this.dateGroupManager, // Передаем в renderer
      profileUrl: options.profileUrl || "/employees/profile/",
      detailUrlTemplate: options.detailUrlTemplate || "/employees/detail/0/",
    });

    this.scrollManager = new ScrollManagerV2({
      scrollElement: this.scrollElement,
      loader: this.loader,
      renderer: this.renderer,
      store: this.store,
      chatId: this.chatId,
    });

    // Состояние
    this._initialized = false;
    this._initializing = false;
    this._destroyed = false;

    // Badge Manager для непрочитанных сообщений
    this.badgeManager = new UnreadBadgeManager("scrollBtn");

    // Слушатели
    this._scrollWatcherCleanup = null;

    // Слушатели для cleanup
    this._eventListeners = [];

    // Подписки
    this._setupStoreSubscription();
    if (options.wsConnection) {
      this._setupWebSocketListeners();
    }

    console.log("[ChatControllerV2] Created for chat:", this.chatId);
  }

  // ==================== Публичное API - Жизненный цикл ====================

  /**
   * Инициализирует чат: загружает сообщения, рендерит, настраивает скролл
   * @returns {Promise<void>}
   */
  async init() {
    if (this._initialized) {
      console.warn("[ChatControllerV2] Already initialized");
      return;
    }

    if (this._initializing) {
      console.warn("[ChatControllerV2] Initialization in progress");
      return;
    }

    this._initializing = true;

    try {
      // 1. Загружаем сообщения
      // Используем timestamp как fallback если нет message ID (API поддерживает оба)
      const anchorValue = this.lastReadMessageId || this.lastReadTimestamp;
      
      console.log('[ChatControllerV2] Init: Loading messages', {
        anchorValue,
        lastReadMessageId: this.lastReadMessageId,
        lastReadTimestamp: this.lastReadTimestamp,
        willLoadAround: !!anchorValue
      });
      
      const loadResult = await this.loader.loadInitial(this.chatId, {
        aroundMessageId: anchorValue,
      });

      // 2. Скрываем контейнер для плавного рендера
      this.scrollElement.classList.add("scroll-hidden");

      try {
        // 3. Рендерим сообщения
        await this.renderer.render(this.chatId);

        // 4. СНАЧАЛА показываем контейнер (важно для scrollTop!)
        this.scrollElement.classList.remove("scroll-hidden");

        // Ждем один frame чтобы браузер применил visibility
        await new Promise((resolve) => requestAnimationFrame(resolve));

        // 5. ✨ НОВЫЙ ПОДХОД: Мгновенное позиционирование БЕЗ скролла
        if (loadResult.anchorId) {
          // Есть lastRead - СРАЗУ позиционируем на него
          await this._positionToMessage(loadResult.anchorId);
        } else {
          // Нет anchor - позиционируем в самый низ (новый чат)
          await new Promise((resolve) => {
            requestAnimationFrame(() => {
              // Отключаем scroll-behavior для мгновенного скролла
              const originalScrollBehavior = this.scrollElement.style.scrollBehavior;
              this.scrollElement.style.scrollBehavior = 'auto';
              
              this.scrollElement.scrollTop = this.scrollElement.scrollHeight;
              
              // Возвращаем scroll-behavior
              requestAnimationFrame(() => {
                this.scrollElement.style.scrollBehavior = originalScrollBehavior;
              });
              
              console.log(
                "[ChatControllerV2] Initial position: bottom (no anchor)"
              );
              resolve();
            });
          });
        }

        // 6. Инициализируем ScrollManager
        await this.scrollManager.init();

        // 7. Инициализируем StickyDateObserver
        this.stickyDateObserver.init();

        // 8. Настраиваем обработчик кликов на даты
        this._setupDateClickHandler();

        // 9. Инициализируем умную кнопку скролла
        this._initScrollButton();

        // 9. Инициализируем watcher для умного автоскролла
        this._initScrollWatcher();
      } catch (error) {
        this.scrollElement.classList.remove("scroll-hidden");
        throw error;
      }

      this._initialized = true;
      this._initializing = false;

      // Dispatch события
      this._emit(CHAT_EVENTS.INITIALIZED, { chatId: this.chatId });

      console.log("[ChatControllerV2] Initialized successfully");
    } catch (error) {
      this._initializing = false;
      console.error("[ChatControllerV2] Initialization failed:", error);
      this._emit(CHAT_EVENTS.ERROR, { error, phase: "init" });
      throw error;
    }
  }

  /**
   * Уничтожает контроллер и освобождает ресурсы
   */
  destroy() {
    if (this._destroyed) return;

    this._destroyed = true;

    // Отменяем активные запросы
    this.loader.cancelAll(this.chatId);

    // Уничтожаем ScrollManager
    this.scrollManager?.destroy();

    // Уничтожаем StickyDateObserver
    this.stickyDateObserver?.destroy();

    // Очищаем DateGroupManager
    this.dateGroupManager?.clear();

    // Очищаем Store
    this.store?.clearChat(this.chatId);

    // Очищаем Renderer
    this.renderer?.clear();

    // Удаляем scroll watcher
    if (this._scrollWatcherCleanup) {
      this._scrollWatcherCleanup();
      this._scrollWatcherCleanup = null;
    }

    // Удаляем слушатели событий
    this._eventListeners.forEach(({ event, handler }) => {
      window.removeEventListener(event, handler);
    });
    this._eventListeners = [];

    console.log("[ChatControllerV2] Destroyed");
  }

  // ==================== Публичное API - Сообщения ====================

  /**
   * Отправляет сообщение
   * @param {string} content - Текст сообщения
   * @param {Object} [options] - Дополнительные опции
   * @returns {string|null} Временный ID или null при ошибке
   */
  sendMessage(content, options = {}) {
    if (!content?.trim()) {
      console.warn("[ChatControllerV2] Cannot send empty message");
      return null;
    }

    const tempId = this.loader.sendOptimistic(
      this.chatId,
      content.trim(),
      options
    );
    return tempId;
  }

  /**
   * Получает сообщение по ID
   * @param {number|string} messageId
   * @returns {Object|null}
   */
  getMessage(messageId) {
    return this.store.getMessage(messageId);
  }

  /**
   * Получает все сообщения чата
   * @param {Object} [options]
   * @returns {Array}
   */
  getMessages(options = {}) {
    return this.store.getMessagesForChat(this.chatId, options);
  }

  // ==================== Публичное API - Скролл ====================

  /**
   * Загружает больше истории
   * @returns {Promise<Array>}
   */
  async loadMoreHistory() {
    return this.scrollManager.loadMoreHistory();
  }

  /**
   * Прокручивает к последнему сообщению
   * @param {Object} [options]
   */
  scrollToBottom(options = {}) {
    this.scrollManager.scrollToBottom(options);
  }

  /**
   * Прокручивает к конкретному сообщению
   * @param {number|string} messageId
   * @param {Object} [options]
   */
  scrollToMessage(messageId, options = {}) {
    this.scrollManager.scrollToMessage(messageId, options);
  }

  /**
   * Проверяет находится ли пользователь внизу чата
   * @returns {boolean}
   */
  isNearBottom() {
    return this.scrollManager.isNearBottom();
  }

  // ==================== Публичное API - Состояние ====================

  /**
   * Получает статус контроллера
   * @returns {Object}
   */
  getStatus() {
    return {
      chatId: this.chatId,
      initialized: this._initialized,
      messageCount: this.store.getMessageCount(this.chatId),
      isLoading: this.loader.isLoading(this.chatId),
      hasMoreHistory: this.loader.hasMoreHistory(this.chatId),
      scroll: this.scrollManager.getStatus(),
      store: this.store.getStats(),
      renderer: this.renderer.getStats(),
    };
  }

  /**
   * Проверяет инициализирован ли контроллер
   * @returns {boolean}
   */
  get isInitialized() {
    return this._initialized;
  }

  // ==================== Приватные методы - Подписки ====================

  /**
   * Настраивает подписку на Store
   * @private
   */
  _setupStoreSubscription() {
    this.store.subscribe((event, data) => {
      // Игнорируем события во время инициализации
      if (this._initializing) return;

      this._handleStoreEvent(event, data);
    });
  }

  /**
   * Обрабатывает события Store
   * @private
   */
  _handleStoreEvent(event, data) {
    switch (event) {
      case "message_added":
        this._onMessageAdded(data);
        break;
      case "message_updated":
        this._onMessageUpdated(data);
        break;
      case "message_removed":
        this._onMessageRemoved(data);
        break;
    }
  }

  /**
   * Обработчик добавления сообщения
   * @private
   */
  _onMessageAdded(data) {
    const { message, optimistic } = data;

    if (message.chat_id !== this.chatId) return;

    // Рендерим новое сообщение
    this.renderer.appendMessage(message, this.chatId);

    // Обновляем StickyDateObserver (могла появиться новая date group)
    if (this.stickyDateObserver?.isInitialized()) {
      this.stickyDateObserver.refresh();
    }

    // УМНЫЙ АВТОСКРОЛЛ:
    // 1. Своё сообщение - всегда скроллим
    // 2. Чужое сообщение + внизу чата - скроллим (активно читаем)
    // 3. Чужое сообщение + читаем историю - показываем индикатор
    const isMyMessage = message.author_id === this.currentUserId;
    const isAtBottom = this.scrollManager.isNearBottom();
    const shouldScroll = isMyMessage || isAtBottom;

    if (shouldScroll) {
      // Для своих сообщений - мгновенный скролл (AUTOSCROLL_CONFIG.SMOOTH_SCROLL_FOR_OWN)
      // Для чужих - проверка уже прошла выше (isAtBottom)
      this.scrollManager.scrollToBottom({
        instant: isMyMessage && !AUTOSCROLL_CONFIG.SMOOTH_SCROLL_FOR_OWN,
        force: isMyMessage,
      });
      // Скрываем индикатор если он показан
      this._hideNewMessagesIndicator();
    } else if (!shouldScroll && !optimistic) {
      // Показываем индикатор только для НЕ-оптимистичных чужих сообщений
      this._showNewMessagesIndicator();
    }

    this._emit(CHAT_EVENTS.MESSAGE_ADDED, {
      messageId: message.id,
      chatId: this.chatId,
    });
  }

  /**
   * Обработчик обновления сообщения
   * @private
   */
  _onMessageUpdated(data) {
    const { messageId, updates } = data;
    this.renderer.updateMessage(messageId, updates);
    this._emit(CHAT_EVENTS.MESSAGE_UPDATED, {
      messageId,
      updates,
      chatId: this.chatId,
    });
  }

  /**
   * Обработчик удаления сообщения
   * @private
   */
  _onMessageRemoved(data) {
    const { messageId } = data;
    this.renderer.removeMessage(messageId);
    this._emit(CHAT_EVENTS.MESSAGE_REMOVED, { messageId, chatId: this.chatId });
  }

  /**
   * Настраивает слушатели WebSocket
   * @private
   */
  _setupWebSocketListeners() {
    const handlers = [
      [WS_EVENTS.NEW_MESSAGE, (e) => this._handleWsNewMessage(e.detail)],
      [WS_EVENTS.MESSAGE_EDITED, (e) => this._handleWsMessageEdited(e.detail)],
      [
        WS_EVENTS.MESSAGE_REMOVED,
        (e) => this._handleWsMessageRemoved(e.detail),
      ],
      [WS_EVENTS.REACTION_ADDED, (e) => this._handleWsReaction(e.detail)],
      [WS_EVENTS.REACTION_REMOVED, (e) => this._handleWsReaction(e.detail)],
    ];

    handlers.forEach(([event, handler]) => {
      window.addEventListener(event, handler);
      this._eventListeners.push({ event, handler });
    });

    // Слушаем событие скролла вниз для сброса badge
    const scrollBottomHandler = (e) => {
      if (e.detail.chatId === this.chatId) {
        this.badgeManager.reset();
      }
    };
    window.addEventListener("chat:userScrolledToBottom", scrollBottomHandler);
    this._eventListeners.push({
      event: "chat:userScrolledToBottom",
      handler: scrollBottomHandler,
    });
  }

  /**
   * @private
   */
  _handleWsNewMessage(detail) {
    const { message, chatId } = detail;
    if (chatId === this.chatId && message) {
      const boundaries = this.loader.chatBoundaries.get(chatId);
      const isInPresentTime = boundaries && !boundaries.hasMoreAfter;

      if (isInPresentTime) {
        // ✅ Настоящее время (hasMoreAfter=false) - обрабатываем как обычно
        this.loader.handleNewMessage(message);

        const isNearBottom = this.scrollManager.isNearBottom();

        if (isNearBottom) {
          // ✅ Пользователь внизу → автоскролл к новому сообщению
          requestAnimationFrame(() => {
            this.scrollElement.scrollTop = this.scrollElement.scrollHeight;
            console.log(
              "[ChatControllerV2] Auto-scrolled to new message (user at bottom)"
            );
          });
        } else {
          // ✅ Пользователь НЕ внизу → показываем badge
          this.badgeManager.increment();
        }
      } else {
        // ❌ Исторический просмотр (hasMoreAfter=true) - НЕ рендерим, только badge
        // Не добавляем в Store (не рендерим), только показываем что есть новые
        this.badgeManager.increment();
        console.log(
          "[ChatControllerV2] New message in historical view - showing badge only"
        );
      }
    }
  }

  /**
   * @private
   */
  _handleWsMessageEdited(detail) {
    const { message, chatId } = detail;
    if (chatId === this.chatId && message) {
      this.loader.handleMessageEdited({ message });
    }
  }

  /**
   * @private
   */
  _handleWsMessageRemoved(detail) {
    const { messageId, chatId } = detail;
    if (chatId === this.chatId && messageId) {
      this.loader.handleMessageRemoved({ message_id: messageId });
    }
  }

  /**
   * @private
   */
  _handleWsReaction(detail) {
    const { messageId, reactionsSummary, chatId } = detail;
    if (chatId === this.chatId && messageId) {
      this.loader.handleReactionChange({
        message_id: messageId,
        reactions_summary: reactionsSummary,
      });
    }
  }

  // ==================== Приватные методы - Утилиты ====================

  /**
   * Валидирует опции конструктора
   * @private
   */
  _validateOptions(options) {
    if (!options.chatId) {
      throw new Error("[ChatControllerV2] chatId is required");
    }
    if (!options.scrollElement) {
      throw new Error("[ChatControllerV2] scrollElement is required");
    }
    if (!options.currentUserId) {
      throw new Error("[ChatControllerV2] currentUserId is required");
    }
  }

  /**
   * 🆕 Мгновенно позиционирует viewport на сообщение БЕЗ скроллинга
   * Вызывается ТОЛЬКО при начальной загрузке
   * @private
   */
  async _positionToMessage(messageId) {
    if (!messageId) return false;

    // Ждем один RAF для надежности
    await new Promise((resolve) => requestAnimationFrame(resolve));

    const messageEl = this.scrollElement.querySelector(
      `[data-message-id="${messageId}"]`
    );

    if (messageEl) {
      // Вычисляем позицию для центрирования сообщения
      const containerRect = this.scrollElement.getBoundingClientRect();
      const messageRect = messageEl.getBoundingClientRect();
      const relativeTop = messageRect.top - containerRect.top;

      // Учитываем sticky header (56px + ~40px для sticky date)
      const stickyHeaderOffset = 96;
      const targetScrollTop =
        this.scrollElement.scrollTop +
        relativeTop -
        this.scrollElement.clientHeight / 2 +
        messageRect.height / 2;

      // Дополнительно вычитаем offset если сообщение будет в верхней части
      const adjustedScrollTop =
        relativeTop < this.scrollElement.clientHeight / 2
          ? targetScrollTop - stickyHeaderOffset
          : targetScrollTop;

      // ✨ ОТКЛЮЧАЕМ scroll-behavior для мгновенного позиционирования
      const originalScrollBehavior = this.scrollElement.style.scrollBehavior;
      this.scrollElement.style.scrollBehavior = 'auto';
      
      // МГНОВЕННАЯ установка позиции - без анимации!
      this.scrollElement.scrollTop = Math.max(0, adjustedScrollTop);
      
      // Возвращаем scroll-behavior через RAF (после применения scrollTop)
      requestAnimationFrame(() => {
        this.scrollElement.style.scrollBehavior = originalScrollBehavior;
      });

      console.log("[ChatControllerV2] Initial position set to message:", {
        messageId,
        scrollTop: this.scrollElement.scrollTop,
        relativeTop,
        noScrollAnimation: true,
      });
      
      // Сохраняем якорный элемент для корректировки при загрузке изображений
      this._anchorElement = messageEl;
      this._anchorOffsetTop = messageEl.offsetTop;
      this._lastScrollHeight = this.scrollElement.scrollHeight;
      
      // Устанавливаем обработчики загрузки изображений
      this._setupImageLoadHandlers();

      return true;
    }

    console.warn(
      "[ChatControllerV2] Message not found for positioning:",
      messageId
    );
    return false;
  }
  
  /**
   * Устанавливает обработчики загрузки изображений для корректировки скролла
   * @private
   */
  _setupImageLoadHandlers() {
    if (!this._anchorElement) return;
    
    // Находим все изображения в чате
    const images = this.scrollElement.querySelectorAll('img.chat-media--image');
    
    console.log('[ChatControllerV2] Setting up image load handlers:', images.length);
    
    images.forEach((img) => {
      if (img.complete) {
        // Изображение уже загружено
        return;
      }
      
      const handler = () => {
        this._adjustScrollForImageLoad();
      };
      
      img.addEventListener('load', handler, { once: true });
      this._imageLoadHandlers.push({ img, handler });
    });
  }
  
  /**
   * Корректирует скролл при загрузке изображения
   * @private
   */
  _adjustScrollForImageLoad() {
    if (!this._anchorElement || !this._anchorElement.isConnected) {
      console.log('[ChatControllerV2] Anchor element lost, stopping adjustments');
      this._cleanupImageHandlers();
      return;
    }
    
    const currentScrollHeight = this.scrollElement.scrollHeight;
    const heightChange = currentScrollHeight - this._lastScrollHeight;
    
    if (heightChange > 0) {
      const currentAnchorOffset = this._anchorElement.offsetTop;
      const anchorDrift = currentAnchorOffset - this._anchorOffsetTop;
      
      if (anchorDrift > 5) { // Игнорируем маленькие изменения
        console.log('[ChatControllerV2] Adjusting scroll for image load:', {
          heightChange,
          anchorDrift,
          oldScrollTop: this.scrollElement.scrollTop,
          newScrollTop: this.scrollElement.scrollTop + anchorDrift
        });
        
        // Корректируем scrollTop чтобы якорь остался на месте
        this.scrollElement.scrollTop += anchorDrift;
        
        // Обновляем отслеживаемые значения
        this._anchorOffsetTop = currentAnchorOffset;
      }
      
      this._lastScrollHeight = currentScrollHeight;
    }
  }
  
  /**
   * Очищает обработчики загрузки изображений
   * @private
   */
  _cleanupImageHandlers() {
    this._imageLoadHandlers.forEach(({ img, handler }) => {
      img.removeEventListener('load', handler);
    });
    this._imageLoadHandlers = [];
    this._anchorElement = null;
  }

  /**
   * Прокручивает к сообщению
   * @private
   */
  async _scrollToMessage(messageId) {
    if (!messageId) return false;

    // Ждем завершения рендера
    await new Promise((resolve) =>
      setTimeout(resolve, SCROLL_CONFIG.SCROLL_RESTORE_DELAY)
    );

    const messageEl = this.scrollElement.querySelector(
      `[data-message-id="${messageId}"]`
    );

    if (messageEl) {
      // ✅ КРИТИЧНО: НЕ используем scrollIntoView() - он скроллит родителей!
      // Вместо этого вручную скроллим только scrollElement
      const containerRect = this.scrollElement.getBoundingClientRect();
      const messageRect = messageEl.getBoundingClientRect();
      const relativeTop = messageRect.top - containerRect.top;

      // Учитываем sticky header (56px + ~40px для sticky date)
      const stickyHeaderOffset = 96;
      const targetScrollTop =
        this.scrollElement.scrollTop +
        relativeTop -
        this.scrollElement.clientHeight / 2 +
        messageRect.height / 2;

      // Дополнительно вычитаем offset если сообщение будет в верхней части
      const adjustedScrollTop =
        relativeTop < this.scrollElement.clientHeight / 2
          ? targetScrollTop - stickyHeaderOffset
          : targetScrollTop;

      // 🚫 REMOVED: Автоскролл к сообщению после loadAround
      // loadAround уже загрузил контекст, сообщение видно
      // Принудительное центрирование мешает естественной навигации
      console.log(
        "[ChatControllerV2] _scrollToMessage removed - context loaded, no forced scroll"
      );

      console.log(
        "[ChatControllerV2] Scrolled to message with sticky header adjustment:",
        {
          messageId,
          relativeTop,
          stickyHeaderOffset,
          targetScrollTop,
          adjustedScrollTop,
        }
      );

      return true;
    }

    return false;
  }

  /**
   * Отправляет событие
   * @private
   */
  _emit(eventName, detail) {
    window.dispatchEvent(new CustomEvent(eventName, { detail }));
  }

  // ==================== Умный scrollBtn с badge ====================

  /**
   * Инициализирует умную кнопку скролла
   * @private
   */
  _initScrollButton() {
    const scrollBtn = document.getElementById("scrollBtn");

    if (!scrollBtn) {
      console.warn("[ChatControllerV2] #scrollBtn not found");
      return;
    }

    // Заменяем обработчик клика на умный
    scrollBtn.onclick = null;
    scrollBtn.addEventListener("click", () => this._handleScrollButtonClick());

    // Настраиваем умную видимость
    this._setupSmartButtonVisibility();

    console.log("[ChatControllerV2] Smart scroll button initialized");
  }

  /**
   * Настраивает умную видимость кнопки
   * @private
   */
  _setupSmartButtonVisibility() {
    const scrollBtn = document.getElementById("scrollBtn");
    if (!scrollBtn) return;

    // Обновляем видимость при скролле
    const updateVisibility = () => {
      const boundaries = this.loader.chatBoundaries.get(this.chatId);
      const hasMoreAfter = boundaries?.hasMoreAfter || false;
      const isNearBottom = this.scrollManager.isNearBottom();

      // Показываем кнопку если:
      // 1. Пользователь НЕ внизу (любой случай)
      // 2. ИЛИ hasMoreAfter=true (даже если внизу)
      const shouldShow = !isNearBottom || hasMoreAfter;

      scrollBtn.classList.toggle("show", shouldShow);
    };

    // Обновляем при скролле
    this.scrollElement.addEventListener("scroll", updateVisibility);

    // Обновляем при загрузке новых сообщений
    window.addEventListener("chat:messagesLoaded", updateVisibility);

    // Начальное обновление
    setTimeout(updateVisibility, 100);
  }

  /**
   * Обработчик клика на умную кнопку
   * @private
   */
  async _handleScrollButtonClick() {
    const boundaries = this.loader.chatBoundaries.get(this.chatId);
    const hasMoreAfter = boundaries?.hasMoreAfter || false;

    if (hasMoreAfter) {
      // 📥 ИСТОРИЧЕСКИЙ НИЗ: Загружаем всю историю до конца
      console.log("[ChatControllerV2] Loading history to present time...");

      try {
        // Загружаем последние сообщения (настоящее время)
        const result = await this.loader.loadLatest(this.chatId, 50);

        // Рендерим новые сообщения
        await this.renderer.render(this.chatId);

        // Скроллим в низ
        await new Promise((resolve) => requestAnimationFrame(resolve));
        this.scrollElement.scrollTop = this.scrollElement.scrollHeight;

        console.log(
          "[ChatControllerV2] Loaded to present, messages:",
          result.messages.length
        );
      } catch (error) {
        console.error("[ChatControllerV2] Failed to load history:", error);
        // Если ошибка - просто скроллим в низ загруженного
        this.scrollElement.scrollTop = this.scrollElement.scrollHeight;
      }

      // Сбрасываем badge
      this.badgeManager.reset();
      return;
    }

    // 🔵 НАСТОЯЩИЙ НИЗ: Умная логика
    const isInPresentTime = !hasMoreAfter;

    if (
      this.badgeManager.hasUnread() &&
      this.lastReadMessageId &&
      isInPresentTime
    ) {
      // Режим "Перейти к непрочитанным"
      // Пытаемся найти первое непрочитанное (lastReadId + 1)
      const firstUnreadId = this.lastReadMessageId + 1;
      const firstUnreadEl = this.scrollElement.querySelector(
        `[data-message-id="${firstUnreadId}"]`
      );

      if (firstUnreadEl) {
        // Скроллим к первому непрочитанному
        const containerRect = this.scrollElement.getBoundingClientRect();
        const messageRect = firstUnreadEl.getBoundingClientRect();
        const relativeTop = messageRect.top - containerRect.top;
        const targetScrollTop =
          this.scrollElement.scrollTop + relativeTop - 100;

        this.scrollElement.scrollTop = Math.max(0, targetScrollTop);
        console.log(
          "[ChatControllerV2] Scrolled to first unread:",
          firstUnreadId
        );
      } else {
        // Не нашли первое непрочитанное - просто в низ
        this.scrollElement.scrollTop = this.scrollElement.scrollHeight;
      }
    } else {
      // Обычный режим "В самый низ"
      this.scrollElement.scrollTop = this.scrollElement.scrollHeight;
      console.log("[ChatControllerV2] Scrolled to bottom");
    }

    // Сбрасываем badge
    this.badgeManager.reset();
  }

  /**
   * Настраивает обработчик кликов на даты
   * @private
   */
  _setupDateClickHandler() {
    // Делегированный обработчик для всех .sticky-date
    this.scrollElement.addEventListener("click", (e) => {
      const stickyDate = e.target.closest(".sticky-date.interactive");
      if (!stickyDate) return;

      const dateText =
        stickyDate.getAttribute("data-date-text") ||
        stickyDate.querySelector("span")?.textContent;

      console.log("[ChatControllerV2] Date clicked:", dateText);

      // Открываем модальное окно с date picker
      this._openDatePickerModal(dateText);
    });
  }

  /**
   * Открывает модальное окно с date picker
   * @private
   */
  _openDatePickerModal(currentDateText) {
    // Ищем или создаем модальное окно
    let modal = document.getElementById("chatDatePickerModal");

    if (!modal) {
      // Создаем модальное окно динамически
      modal = this._createDatePickerModal();
      document.body.appendChild(modal);
    }

    // Инициализируем Bootstrap modal
    const bsModal = new bootstrap.Modal(modal);

    // Устанавливаем текущую дату как заголовок
    const modalTitle = modal.querySelector(".modal-title");
    if (modalTitle) {
      modalTitle.textContent = `Перейти к дате (текущая: ${currentDateText})`;
    }

    // Обработчик подтверждения
    const confirmBtn = modal.querySelector("#confirmDateJump");
    const dateInput = modal.querySelector("#chatDateInput");

    if (confirmBtn && dateInput) {
      // Устанавливаем сегодняшнюю дату по умолчанию
      dateInput.valueAsDate = new Date();

      // Удаляем старые обработчики
      const newConfirmBtn = confirmBtn.cloneNode(true);
      confirmBtn.parentNode.replaceChild(newConfirmBtn, confirmBtn);

      // Добавляем новый обработчик
      newConfirmBtn.addEventListener("click", () => {
        const selectedDate = dateInput.valueAsDate;
        if (selectedDate) {
          bsModal.hide();
          this._jumpToDate(selectedDate);
        }
      });
    }

    // Показываем модальное окно
    bsModal.show();
  }

  /**
   * Создает модальное окно date picker
   * @private
   */
  _createDatePickerModal() {
    const modal = document.createElement("div");
    modal.id = "chatDatePickerModal";
    modal.className = "modal fade";
    modal.tabIndex = -1;
    modal.setAttribute("aria-hidden", "true");

    modal.innerHTML = `
            <div class="modal-dialog modal-dialog-centered">
                <div class="modal-content">
                    <div class="modal-header">
                        <h5 class="modal-title">
                            <i class="bi-calendar3 me-2"></i>Перейти к дате
                        </h5>
                        <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                    </div>
                    <div class="modal-body">
                        <div class="mb-3">
                            <label for="chatDateInput" class="form-label">Выберите дату</label>
                            <input type="date" class="form-control" id="chatDateInput" required>
                            <div class="form-text">
                                Чат загрузит сообщения вокруг выбранной даты
                            </div>
                        </div>
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">
                            Отмена
                        </button>
                        <button type="button" class="btn btn-primary" id="confirmDateJump">
                            <i class="bi-arrow-right-circle me-1"></i>Перейти
                        </button>
                    </div>
                </div>
            </div>
        `;

    return modal;
  }

  /**
   * Переходит к указанной дате
   * @private
   */
  async _jumpToDate(targetDate) {
    console.log("[ChatControllerV2] Jumping to date:", targetDate);

    // Конвертируем дату в timestamp (начало дня по UTC)
    const timestamp = Date.UTC(
      targetDate.getFullYear(),
      targetDate.getMonth(),
      targetDate.getDate()
    );

    try {
      // Показываем индикатор загрузки
      const loader = this.scrollElement.querySelector("[data-history-loader]");
      if (loader) {
        loader.classList.remove("d-none");
      }

      // КРИТИЧНО: Очищаем Store чтобы не смешивать старые и новые сообщения
      // Как в Telegram Web - при переходе к дате чат перезагружается с этой точки
      this.store.clearChat(this.chatId);

      // Загружаем сообщения вокруг этой даты через API
      // Сообщения автоматически попадут в Store
      const loadResult = await this.loader.loadAround(this.chatId, timestamp);

      if (loadResult.messages && loadResult.messages.length > 0) {
        console.log(
          "[ChatControllerV2] Loaded messages around date:",
          loadResult.messages.length
        );

        // Перерисовываем чат из Store (как в Telegram Web)
        await this.renderer.render(this.chatId);

        // КРИТИЧНО: Переинициализируем ScrollManager для новых сообщений
        // Сбрасываем флаг инициализации
        if (this.scrollManager._isInitializing !== undefined) {
          this.scrollManager._isInitializing = false;
        }

        // Переподключаем IntersectionObserver к новому первому сообщению
        if (this.scrollManager._setupIntersectionObserver) {
          this.scrollManager._setupIntersectionObserver();
        }

        // Даем время на завершение рендеринга
        await new Promise((resolve) => requestAnimationFrame(resolve));

        // Якорное сообщение (возвращается API)
        const anchorMessageId =
          loadResult.anchorId || loadResult.messages[0].id;

        // Скроллим к якорному сообщению БЕЗ smooth (мгновенно)
        this.scrollManager.scrollToMessage(anchorMessageId, {
          block: "start",
          behavior: "auto",
        });

        // КРИТИЧНО: Приостанавливаем обработку скролла на 1 секунду
        // чтобы не сработал автоматический loadNewer
        this.scrollManager.pauseScrollEvents(1000);

        console.log(
          "[ChatControllerV2] Jumped to date, anchor message:",
          anchorMessageId
        );
      } else {
        // Нет сообщений в эту дату
        alert("В выбранную дату нет сообщений");
      }
    } catch (error) {
      console.error("[ChatControllerV2] Error jumping to date:", error);
      alert("Ошибка при переходе к дате");
    } finally {
      // Скрываем индикатор
      const loader = this.scrollElement.querySelector("[data-history-loader]");
      if (loader) {
        loader.classList.add("d-none");
      }
    }
  }

  /**
   * Показывает индикатор новых сообщений
   * @private
   */
  _showNewMessagesIndicator() {
    if (!this._newMessagesCount) {
      this._newMessagesCount = 0;
    }
    this._newMessagesCount++;
    
    // Можно добавить UI индикатор или просто считать
    console.log('[ChatControllerV2] New messages indicator:', this._newMessagesCount);
    
    // TODO: Показать визуальный индикатор в UI если нужно
    // const indicator = document.getElementById('newMessagesIndicator');
    // if (indicator) {
    //   indicator.textContent = `${this._newMessagesCount} новых сообщений`;
    //   indicator.classList.add('show');
    // }
  }

  /**
   * Скрывает индикатор новых сообщений
   * @private
   */
  _hideNewMessagesIndicator() {
    this._newMessagesCount = 0;
    
    console.log('[ChatControllerV2] New messages indicator hidden');
    
    // TODO: Скрыть визуальный индикатор в UI если есть
    // const indicator = document.getElementById('newMessagesIndicator');
    // if (indicator) {
    //   indicator.classList.remove('show');
    // }
  }

  /**
   * Инициализирует отслеживание скролла для индикатора
   * @private
   */
  _initScrollWatcher() {
    // Слушаем скролл для автоматического скрытия индикатора
    const scrollHandler = () => {
      if (this.scrollManager.isNearBottom() && this._newMessagesCount > 0) {
        this._hideNewMessagesIndicator();
      }
    };

    this.scrollElement.addEventListener("scroll", scrollHandler);

    // Сохраняем handler для cleanup
    this._scrollWatcherCleanup = () => {
      this.scrollElement.removeEventListener("scroll", scrollHandler);
    };
  }
}

export default ChatControllerV2;
