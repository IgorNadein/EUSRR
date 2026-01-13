/**
 * @fileoverview Chat Module Index - точка входа для всех модулей чата
 * @module chat/index
 * 
 * ⚠️ МИГРАЦИЯ НА V2 ЗАВЕРШЕНА
 * 
 * V2 версии теперь являются ОСНОВНЫМИ (рекомендуется использовать)
 * Legacy версии (без V2) доступны для обратной совместимости
 * 
 * Использование:
 * 
 * // Рекомендуемый способ (V2):
 * import { ChatController, MessageStore } from './chat/index.js';
 * 
 * // Legacy (старый код):
 * import { ChatControllerLegacy, MessageStoreLegacy } from './chat/index.js';
 * 
 * // Миграция существующих контроллеров:
 * import { migrateToV2 } from './utils/chatMigration.js';
 * const v2Controller = migrateToV2(oldController);
 */

// Конфигурация
export { 
    LOADER_CONFIG,
    SCROLL_CONFIG,
    AUTOSCROLL_CONFIG, // НОВОЕ: настройки умного автоскролла
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

// ==================== V2 (ОСНОВНЫЕ) ====================

// Controllers
export { ChatControllerV2 as ChatController } from '../controllers/chatControllerV2.js';

// Store
export { MessageStoreV2 as MessageStore } from '../stores/messageStoreV2.js';

// Loader
export { MessageLoaderV2 as MessageLoader } from '../loaders/messageLoaderV2.js';

// Managers
export { ScrollManagerV2 as ScrollManager } from '../managers/scrollManagerV2.js';

// Renderer (используется обеими версиями)
export { MessageRendererV2 as MessageRenderer } from '../renderers/messageRendererV2.js';

// ==================== LEGACY (ОБРАТНАЯ СОВМЕСТИМОСТЬ) ====================
// DEPRECATED: Старые файлы переименованы в .legacy.js

export { ChatController as ChatControllerLegacy } from '../controllers/chatController.js';
export { MessageStore as MessageStoreLegacy } from '../stores/messageStore.js';
export { MessageLoaderV2 as MessageLoaderLegacy } from '../loaders/messageLoaderV2.js';
export { ScrollManagerV2 as ScrollManagerLegacy } from '../managers/scrollManagerV2.js';

// ==================== МИГРАЦИОННЫЕ УТИЛИТЫ ====================

export {
    migrateToV2,
    migrateOptions,
    ChatControllerCompat,
    isV2Controller,
    isLegacyController,
    getControllerVersion
} from '../utils/chatMigration.js';

/**
 * Создает экземпляр ChatController с рекомендуемыми настройками
 * @param {Object} options - Опции
 * @returns {Promise<ChatController>} V2 контроллер (по умолчанию)
 */
export async function createChatController(options) {
    // Импортируем динамически чтобы избежать циклических зависимостей
    const { ChatControllerV2 } = await import('../controllers/chatControllerV2.js');
    return new ChatControllerV2(options);
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
    description: 'Модуль загрузки и управления чатом (V2 с умным автоскроллом)',
    components: [
        'ChatController (V2)',
        'MessageStore (V2)',
        'MessageLoader (V2)',
        'ScrollManager (V2)',
        'MessageRenderer (V2)'
    ],
    features: [
        '✅ Умный автоскролл (как в Telegram)',
        '✅ Индикатор новых сообщений',
        '✅ Batch операции (3x быстрее)',
        '✅ Retry логика с exponential backoff',
        '✅ AbortController для отмены запросов',
        '✅ Централизованная конфигурация',
        '✅ Debounce/throttle для scroll events'
    ],
    migration: {
        status: 'completed',
        date: '2026-01-13',
        guide: 'backend/docs/guides/V2_MIGRATION_GUIDE.md'
    }
};
