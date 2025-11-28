/**
 * @fileoverview DataManager - централизованное управление данными с кешированием и дедупликацией
 * Предотвращает дублирование запросов и обеспечивает кеширование на клиенте
 * @module managers/dataManager
 */

/**
 * Менеджер данных с кешированием и дедупликацией запросов
 */
class DataManager {
  constructor() {
    /** @type {Map<string, {data: any, timestamp: number}>} */
    this.cache = new Map();
    
    /** @type {Map<string, Promise<any>>} */
    this.pending = new Map();
    
    /** @type {number} */
    this.defaultTTL = 30000; // 30 секунд по умолчанию
    
    // Подписчики на изменения данных
    this.subscribers = new Map();
  }

  /**
   * Получить данные с кешированием и дедупликацией
   * @param {string} key - Уникальный ключ для данных
   * @param {Function} fetchFn - Функция для загрузки данных (должна возвращать Promise)
   * @param {number} [ttl] - Time to live в миллисекундах (по умолчанию 30000)
   * @returns {Promise<any>} Данные
   */
  async fetch(key, fetchFn, ttl = this.defaultTTL) {
    // 1. Проверяем кеш
    if (this.cache.has(key)) {
      const { data, timestamp } = this.cache.get(key);
      const age = Date.now() - timestamp;
      
      if (age < ttl) {
        console.log(`[DataManager] Cache HIT: ${key} (age: ${age}ms)`);
        return data;
      } else {
        console.log(`[DataManager] Cache EXPIRED: ${key} (age: ${age}ms, ttl: ${ttl}ms)`);
        this.cache.delete(key);
      }
    }
    
    // 2. Проверяем pending запросы (дедупликация)
    if (this.pending.has(key)) {
      console.log(`[DataManager] Request DEDUPED: ${key}`);
      return this.pending.get(key);
    }
    
    // 3. Делаем запрос
    console.log(`[DataManager] Fetching: ${key}`);
    const promise = fetchFn()
      .then(data => {
        // Сохраняем в кеш
        this.cache.set(key, { 
          data, 
          timestamp: Date.now() 
        });
        
        // Удаляем из pending
        this.pending.delete(key);
        
        // Уведомляем подписчиков
        this.notify(key, data);
        
        return data;
      })
      .catch(error => {
        // Удаляем из pending при ошибке
        this.pending.delete(key);
        throw error;
      });
    
    // Сохраняем promise в pending
    this.pending.set(key, promise);
    
    return promise;
  }

  /**
   * Инвалидировать кеш для ключа
   * @param {string} key - Ключ данных
   */
  invalidate(key) {
    console.log(`[DataManager] Invalidating: ${key}`);
    this.cache.delete(key);
    this.notify(key, null);
  }

  /**
   * Инвалидировать все ключи, соответствующие паттерну
   * @param {RegExp|string} pattern - Паттерн для поиска ключей
   */
  invalidatePattern(pattern) {
    const regex = typeof pattern === 'string' 
      ? new RegExp(pattern) 
      : pattern;
    
    const keysToInvalidate = Array.from(this.cache.keys())
      .filter(key => regex.test(key));
    
    console.log(`[DataManager] Invalidating pattern "${pattern}":`, keysToInvalidate);
    
    keysToInvalidate.forEach(key => {
      this.cache.delete(key);
      this.notify(key, null);
    });
  }

  /**
   * Очистить весь кеш
   */
  clear() {
    console.log('[DataManager] Clearing all cache');
    this.cache.clear();
    this.pending.clear();
  }

  /**
   * Подписаться на изменения данных
   * @param {string} key - Ключ данных
   * @param {Function} callback - Коллбек (data) => void
   * @returns {Function} Функция отписки
   */
  subscribe(key, callback) {
    if (!this.subscribers.has(key)) {
      this.subscribers.set(key, new Set());
    }
    
    this.subscribers.get(key).add(callback);
    
    // Возвращаем функцию отписки
    return () => {
      const subs = this.subscribers.get(key);
      if (subs) {
        subs.delete(callback);
        if (subs.size === 0) {
          this.subscribers.delete(key);
        }
      }
    };
  }

  /**
   * Уведомить подписчиков об изменении данных
   * @param {string} key - Ключ данных
   * @param {any} data - Новые данные
   * @private
   */
  notify(key, data) {
    const subs = this.subscribers.get(key);
    if (subs) {
      subs.forEach(callback => {
        try {
          callback(data);
        } catch (err) {
          console.error(`[DataManager] Subscriber error for key "${key}":`, err);
        }
      });
    }
  }

  /**
   * Получить статистику кеша
   * @returns {Object} Статистика
   */
  getStats() {
    return {
      cacheSize: this.cache.size,
      pendingCount: this.pending.size,
      subscribersCount: this.subscribers.size,
      keys: Array.from(this.cache.keys())
    };
  }

  /**
   * Пре-загрузить данные в кеш
   * @param {string} key - Ключ данных
   * @param {any} data - Данные для сохранения
   */
  preload(key, data) {
    console.log(`[DataManager] Preloading: ${key}`);
    this.cache.set(key, {
      data,
      timestamp: Date.now()
    });
  }
}

// Экспортируем singleton
export const dataManager = new DataManager();

// Для отладки в консоли
if (typeof window !== 'undefined') {
  window.dataManager = dataManager;
}
