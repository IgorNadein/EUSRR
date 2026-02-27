/**
 * @fileoverview Миграционный слой для перехода с ChatController на ChatControllerV2
 * @module utils/chatMigration
 */

import { ChatControllerV2 } from '../controllers/chatControllerV2.js';
import { ChatController } from '../controllers/chatController.js';

/**
 * Мигрирует существующий экземпляр ChatController на V2
 * @param {ChatController} oldController - Старый контроллер
 * @returns {ChatControllerV2} Новый контроллер V2
 */
export function migrateToV2(oldController) {
    if (!oldController) {
        throw new Error('[Migration] oldController is required');
    }

    console.log('[Migration] Starting migration to V2...');

    // Извлекаем состояние из старого контроллера
    const state = {
        chatId: oldController.chatId,
        currentUserId: oldController.currentUserId,
        scrollElement: oldController.scrollElement,
        containerId: oldController.containerId,
        lastReadMessageId: oldController.lastReadTimestamp // V2 использует ID вместо timestamp
    };

    // Сохраняем состояние скролла
    const scrollPosition = oldController.scrollElement.scrollTop;
    const scrollHeight = oldController.scrollElement.scrollHeight;
    const wasAtBottom = oldController.scrollManager?.isNearBottom() || false;

    // Уничтожаем старый контроллер
    oldController.destroy();
    console.log('[Migration] Old controller destroyed');

    // Создаем новый контроллер V2
    const v2Controller = new ChatControllerV2(state);
    console.log('[Migration] V2 controller created');

    // Восстанавливаем позицию скролла после инициализации
    v2Controller.init().then(() => {
        if (wasAtBottom) {
            v2Controller.scrollManager.scrollToBottom({ instant: true });
        } else {
            // Пытаемся восстановить относительную позицию
            const relativePosition = scrollPosition / scrollHeight;
            const newScrollTop = v2Controller.scrollElement.scrollHeight * relativePosition;
            v2Controller.scrollElement.scrollTop = newScrollTop;
        }
        console.log('[Migration] ✅ Migration complete!');
    });

    return v2Controller;
}

/**
 * Преобразует старые опции в новый формат
 * @param {Object} legacyOptions - Опции в старом формате
 * @returns {Object} Опции в формате V2
 */
export function migrateOptions(legacyOptions) {
    const v2Options = { ...legacyOptions };

    // Преобразуем lastReadTimestamp → lastReadMessageId
    if (legacyOptions.lastReadTimestamp && !legacyOptions.lastReadMessageId) {
        // В V2 используется ID, если у нас только timestamp - игнорируем
        v2Options.lastReadMessageId = null;
    }

    // Удаляем устаревшие поля
    delete v2Options.lastReadTimestamp;

    return v2Options;
}

/**
 * Compatibility wrapper - позволяет использовать V2 как старый ChatController
 * Для постепенной миграции кода
 */
export class ChatControllerCompat extends ChatControllerV2 {
    constructor(options) {
        // Преобразуем опции
        const v2Options = migrateOptions(options);
        super(v2Options);

        // Добавляем алиасы для обратной совместимости
        this.scrollEl = this.scrollElement; // Старый алиас
        this.initialized = false; // Публичный флаг вместо _initialized
        this.isInitializing = false; // Публичный флаг вместо _initializing

        // Проксируем приватные свойства для старого кода
        Object.defineProperty(this, 'newMessagesCount', {
            get: () => this._newMessagesCount,
            set: (value) => { this._newMessagesCount = value; }
        });

        Object.defineProperty(this, 'newMessagesBtn', {
            get: () => this._newMessagesBtn,
            set: (value) => { this._newMessagesBtn = value; }
        });

        console.log('[ChatControllerCompat] Created with compatibility layer');
    }

    /**
     * Переопределяем init() для обновления публичных флагов
     */
    async init() {
        this.isInitializing = true;
        try {
            await super.init();
            this.initialized = true;
            this.isInitializing = false;
        } catch (error) {
            this.isInitializing = false;
            throw error;
        }
    }

    /**
     * Добавляем методы для обратной совместимости
     */
    getStatus() {
        return {
            chatId: this.chatId,
            initialized: this.initialized,
            messageCount: this.store.messages.size,
            isLoading: false, // V2 не имеет централизованного isLoading
            hasMoreHistory: true, // V2 всегда может попробовать загрузить
            scroll: {
                isNearBottom: this.scrollManager.isNearBottom(),
                scrollTop: this.scrollElement.scrollTop,
                scrollHeight: this.scrollElement.scrollHeight
            },
            store: {
                totalMessages: this.store.messages.size,
                chats: this.store.chatIndex.size
            }
        };
    }

    /**
     * Алиас для совместимости
     */
    _dispatchEvent(eventName, detail) {
        this._emit(eventName, detail);
    }
}

/**
 * Проверяет, является ли контроллер V2
 * @param {Object} controller - Контроллер для проверки
 * @returns {boolean}
 */
export function isV2Controller(controller) {
    return controller instanceof ChatControllerV2;
}

/**
 * Проверяет, является ли контроллер legacy (старым)
 * @param {Object} controller - Контроллер для проверки
 * @returns {boolean}
 */
export function isLegacyController(controller) {
    return controller instanceof ChatController && !(controller instanceof ChatControllerV2);
}

/**
 * Получает версию контроллера
 * @param {Object} controller - Контроллер
 * @returns {string} 'v2' | 'legacy' | 'unknown'
 */
export function getControllerVersion(controller) {
    if (isV2Controller(controller)) return 'v2';
    if (isLegacyController(controller)) return 'legacy';
    return 'unknown';
}

/**
 * Создает правильный контроллер в зависимости от флага миграции
 * @param {Object} options - Опции создания
 * @param {boolean} [options.useV2=false] - Использовать V2
 * @returns {ChatController|ChatControllerV2}
 */
export function createChatController(options) {
    const useV2 = options.useV2 || false;
    delete options.useV2;

    if (useV2) {
        console.log('[Factory] Creating V2 controller');
        return new ChatControllerV2(migrateOptions(options));
    } else {
        console.log('[Factory] Creating legacy controller');
        return new ChatController(options);
    }
}

// Экспорты
export default {
    migrateToV2,
    migrateOptions,
    ChatControllerCompat,
    isV2Controller,
    isLegacyController,
    getControllerVersion,
    createChatController
};

console.log('✅ Chat migration utilities loaded');
