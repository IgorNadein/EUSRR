/**
 * @fileoverview Chat Module Index - точка входа для всех модулей чата
 * @module chat/index
 * 
 * Экспортирует все V2 модули для удобного импорта:
 * 
 * import { ChatControllerV2, MessageStoreV2 } from './chat/index.js';
 */

// Конфигурация
export { 
    LOADER_CONFIG,
    SCROLL_CONFIG,
    RENDER_CONFIG,
    WS_CONFIG,
    STORE_EVENTS,
    CHAT_EVENTS,
    WS_EVENTS,
    MESSAGE_STATUS,
    API_ENDPOINTS,
    buildUrl,
    getRequestHeaders
} from '../config/chatConfig.js';

// Store
export { MessageStoreV2 } from '../stores/messageStoreV2.js';
export { MessageStore } from '../stores/messageStore.js'; // Legacy

// Loader
export { MessageLoaderV2 } from '../loaders/messageLoaderV2.js';
export { MessageLoader } from '../loaders/messageLoader.js'; // Legacy

// Renderer
export { MessageRendererV2 } from '../renderers/messageRendererV2.js';

// Managers
export { ScrollManagerV2 } from '../managers/scrollManagerV2.js';
export { ScrollManager } from '../managers/scrollManager.js'; // Legacy

// Controllers
export { ChatControllerV2 } from '../controllers/chatControllerV2.js';
export { ChatController } from '../controllers/chatController.js'; // Legacy

/**
 * Создает экземпляр ChatController с рекомендуемыми настройками
 * @param {Object} options - Опции
 * @returns {ChatControllerV2}
 */
export function createChatController(options) {
    return new (ChatControllerV2)(options);
}

/**
 * Версия модуля
 */
export const VERSION = '2.0.0';

/**
 * Информация о модуле
 */
export const MODULE_INFO = {
    name: 'EUSRR Chat Module',
    version: VERSION,
    description: 'Модуль загрузки и управления чатом',
    components: [
        'ChatControllerV2',
        'MessageStoreV2',
        'MessageLoaderV2',
        'ScrollManagerV2',
        'MessageRendererV2'
    ]
};
