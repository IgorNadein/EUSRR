/**
 * Timing Utilities
 * 
 * Утилиты для управления временем выполнения функций: debounce, throttle и т.д.
 * 
 * Использование:
 * import { debounce, throttle } from '{% static "js/utils/timing.js" %}';
 */

/**
 * Debounce - откладывает выполнение функции до окончания "тишины"
 * Используется для оптимизации обработчиков событий (поиск, resize, scroll и т.д.)
 * 
 * @param {Function} fn - функция для выполнения
 * @param {number} ms - задержка в миллисекундах (по умолчанию 300)
 * @returns {Function} - обёрнутая функция
 * 
 * @example
 * const handleSearch = debounce((query) => {
 *   console.log('Searching for:', query);
 * }, 300);
 * 
 * // При быстром наборе будет вызван только последний
 * handleSearch('a');    // не выполнится
 * handleSearch('ab');   // не выполнится
 * handleSearch('abc');  // выполнится через 300мс после последнего вызова
 */
export function debounce(fn, ms = 300) {
  let timeout;
  return function(...args) {
    clearTimeout(timeout);
    timeout = setTimeout(() => fn.apply(this, args), ms);
  };
}

/**
 * Throttle - ограничивает частоту выполнения функции
 * Гарантирует выполнение не чаще чем раз в указанный интервал
 * 
 * @param {Function} fn - функция для выполнения
 * @param {number} ms - минимальный интервал между вызовами (по умолчанию 300)
 * @returns {Function} - обёрнутая функция
 * 
 * @example
 * const handleScroll = throttle(() => {
 *   console.log('Scroll position:', window.scrollY);
 * }, 100);
 * 
 * // При скролле будет вызываться максимум раз в 100мс
 * window.addEventListener('scroll', handleScroll);
 */
export function throttle(fn, ms = 300) {
  let inThrottle;
  let lastFn;
  let lastTime;
  
  return function(...args) {
    const context = this;
    
    if (!inThrottle) {
      fn.apply(context, args);
      lastTime = Date.now();
      inThrottle = true;
    } else {
      clearTimeout(lastFn);
      lastFn = setTimeout(() => {
        if (Date.now() - lastTime >= ms) {
          fn.apply(context, args);
          lastTime = Date.now();
        }
      }, Math.max(ms - (Date.now() - lastTime), 0));
    }
  };
}

/**
 * Delay - создаёт Promise, который разрешается через указанное время
 * Полезно для async/await паттернов
 * 
 * @param {number} ms - задержка в миллисекундах
 * @returns {Promise} - Promise, который разрешится через указанное время
 * 
 * @example
 * async function loadData() {
 *   console.log('Loading...');
 *   await delay(1000);
 *   console.log('Loaded!');
 * }
 */
export function delay(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

/**
 * Polling - периодический вызов функции до выполнения условия
 * 
 * @param {Function} fn - функция для выполнения (должна возвращать boolean)
 * @param {number} interval - интервал между вызовами в мс
 * @param {number} timeout - максимальное время ожидания в мс
 * @returns {Promise<boolean>} - Promise, который разрешится когда fn вернёт true
 * 
 * @example
 * // Ждём пока элемент появится в DOM
 * await poll(
 *   () => document.querySelector('#myElement') !== null,
 *   100,  // проверяем каждые 100мс
 *   5000  // максимум 5 секунд
 * );
 */
export function poll(fn, interval = 100, timeout = 5000) {
  const startTime = Date.now();
  
  return new Promise((resolve, reject) => {
    const checkCondition = () => {
      if (fn()) {
        resolve(true);
      } else if (Date.now() - startTime >= timeout) {
        reject(new Error('Polling timeout'));
      } else {
        setTimeout(checkCondition, interval);
      }
    };
    
    checkCondition();
  });
}

/**
 * Once - гарантирует однократное выполнение функции
 * 
 * @param {Function} fn - функция для выполнения
 * @returns {Function} - обёрнутая функция
 * 
 * @example
 * const initialize = once(() => {
 *   console.log('Initialized!');
 * });
 * 
 * initialize(); // выведет "Initialized!"
 * initialize(); // ничего не произойдёт
 */
export function once(fn) {
  let called = false;
  let result;
  
  return function(...args) {
    if (!called) {
      called = true;
      result = fn.apply(this, args);
    }
    return result;
  };
}
