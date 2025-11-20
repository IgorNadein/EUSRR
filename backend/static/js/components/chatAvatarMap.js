/**
 * @fileoverview Chat Avatar Map - Управление картой аватаров пользователей в чате
 * Простой модуль для хранения и получения URL аватаров по user ID
 * @module components/chatAvatarMap
 */

/**
 * Глобальная карта аватаров пользователей
 * @type {Object.<string, string>}
 */
const AVATAR_MAP = {};

/**
 * Устанавливает аватар для пользователя
 * @param {string|number} userId - ID пользователя
 * @param {string} avatarUrl - URL аватара
 */
export function setChatAvatar(userId, avatarUrl) {
  if (!userId) {
    console.warn('setChatAvatar: userId is required');
    return;
  }
  AVATAR_MAP[String(userId)] = avatarUrl || '';
}

/**
 * Получает URL аватара пользователя
 * @param {string|number} userId - ID пользователя
 * @returns {string|null} URL аватара или null если не найден
 */
export function getChatAvatar(userId) {
  if (!userId) return null;
  return AVATAR_MAP[String(userId)] || null;
}

/**
 * Получает всю карту аватаров
 * @returns {Object.<string, string>} Карта userId → avatarUrl
 */
export function getChatAvatarMap() {
  return { ...AVATAR_MAP };
}

/**
 * Очищает карту аватаров
 */
export function clearChatAvatars() {
  Object.keys(AVATAR_MAP).forEach(key => delete AVATAR_MAP[key]);
}

/**
 * Инициализирует карту аватаров с начальными данными
 * @param {Object.<string, string>} initialMap - Начальная карта userId → avatarUrl
 * @returns {Object} API для работы с аватарами
 */
export function initChatAvatarMap(initialMap = {}) {
  // Заполняем начальными данными
  Object.entries(initialMap).forEach(([userId, avatarUrl]) => {
    setChatAvatar(userId, avatarUrl);
  });

  // Экспортируем в window для обратной совместимости
  window.__CHAT_AVATARS__ = AVATAR_MAP;

  return {
    set: setChatAvatar,
    get: getChatAvatar,
    getAll: getChatAvatarMap,
    clear: clearChatAvatars
  };
}

// Публикуем в window для совместимости
if (typeof window !== 'undefined') {
  window.initChatAvatarMap = initChatAvatarMap;
  window.getChatAvatar = getChatAvatar;
  window.setChatAvatar = setChatAvatar;
}
