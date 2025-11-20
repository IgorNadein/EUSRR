/**
 * Scroll Utilities
 * 
 * Утилиты для работы с прокруткой страницы
 * 
 * Использование:
 * import { smoothScrollTo, scrollToTop } from '{% static "js/utils/scroll.js" %}';
 */

/**
 * Плавная прокрутка к элементу с учётом фиксированного navbar
 * 
 * @param {HTMLElement|string} target - элемент или селектор для прокрутки
 * @param {Object} options - опции прокрутки
 * @param {number} options.offset - дополнительный отступ сверху (по умолчанию 20)
 * @param {string} options.behavior - тип прокрутки ('smooth' или 'auto')
 * @returns {void}
 * 
 * @example
 * // Прокрутка к элементу
 * smoothScrollTo('#section2');
 * 
 * // С дополнительным отступом
 * smoothScrollTo(document.querySelector('.target'), { offset: 50 });
 */
export function smoothScrollTo(target, options = {}) {
  const element = typeof target === 'string' 
    ? document.querySelector(target)
    : target;
  
  if (!element) {
    console.warn('smoothScrollTo: element not found', target);
    return;
  }
  
  const {
    offset = 20,
    behavior = 'smooth'
  } = options;
  
  // Высота фиксированного navbar (если есть)
  const navbar = document.querySelector('.app-navbar, .navbar-fixed-top, .fixed-top');
  const navbarHeight = navbar?.offsetHeight || 0;
  
  // Позиция элемента относительно верха документа
  const elementTop = element.getBoundingClientRect().top + window.pageYOffset;
  
  // Финальная позиция с учётом navbar и offset
  const scrollToPosition = elementTop - navbarHeight - offset;
  
  window.scrollTo({
    top: scrollToPosition,
    behavior: behavior
  });
}

/**
 * Прокрутка в начало страницы
 * 
 * @param {boolean} smooth - плавная прокрутка (по умолчанию true)
 * @returns {void}
 * 
 * @example
 * scrollToTop(); // плавная прокрутка вверх
 * scrollToTop(false); // мгновенная прокрутка
 */
export function scrollToTop(smooth = true) {
  window.scrollTo({
    top: 0,
    behavior: smooth ? 'smooth' : 'auto'
  });
}

/**
 * Прокрутка в конец страницы
 * 
 * @param {boolean} smooth - плавная прокрутка (по умолчанию true)
 * @returns {void}
 * 
 * @example
 * scrollToBottom(); // плавная прокрутка вниз
 */
export function scrollToBottom(smooth = true) {
  window.scrollTo({
    top: document.documentElement.scrollHeight,
    behavior: smooth ? 'smooth' : 'auto'
  });
}

/**
 * Проверка видимости элемента в viewport
 * 
 * @param {HTMLElement} element - элемент для проверки
 * @param {number} threshold - процент видимости (0-1)
 * @returns {boolean} - виден ли элемент
 * 
 * @example
 * if (isElementInViewport(element, 0.5)) {
 *   console.log('Элемент виден более чем на 50%');
 * }
 */
export function isElementInViewport(element, threshold = 0) {
  const rect = element.getBoundingClientRect();
  const windowHeight = window.innerHeight || document.documentElement.clientHeight;
  const windowWidth = window.innerWidth || document.documentElement.clientWidth;
  
  const vertInView = (rect.top <= windowHeight) && ((rect.top + rect.height) >= 0);
  const horInView = (rect.left <= windowWidth) && ((rect.left + rect.width) >= 0);
  
  if (threshold === 0) {
    return vertInView && horInView;
  }
  
  // Процент видимости
  const visibleHeight = Math.min(rect.bottom, windowHeight) - Math.max(rect.top, 0);
  const visibleWidth = Math.min(rect.right, windowWidth) - Math.max(rect.left, 0);
  const visibleArea = visibleHeight * visibleWidth;
  const totalArea = rect.height * rect.width;
  
  return (visibleArea / totalArea) >= threshold;
}

/**
 * Получение текущей позиции скролла
 * 
 * @returns {Object} - объект с координатами { x, y }
 * 
 * @example
 * const { x, y } = getScrollPosition();
 * console.log('Scrolled:', x, y);
 */
export function getScrollPosition() {
  return {
    x: window.pageXOffset || document.documentElement.scrollLeft,
    y: window.pageYOffset || document.documentElement.scrollTop
  };
}

/**
 * Скрытие/показ элемента при прокрутке (например, кнопки "наверх")
 * 
 * @param {HTMLElement} element - элемент для показа/скрытия
 * @param {number} threshold - порог прокрутки в пикселях
 * @param {Function} callback - функция обратного вызова
 * @returns {Function} - функция для отписки от события
 * 
 * @example
 * const btn = document.querySelector('#backToTop');
 * const unsubscribe = onScrollThreshold(btn, 300, (visible) => {
 *   btn.style.display = visible ? 'block' : 'none';
 * });
 */
export function onScrollThreshold(element, threshold, callback) {
  const handleScroll = () => {
    const scrollY = window.pageYOffset || document.documentElement.scrollTop;
    callback(scrollY > threshold);
  };
  
  window.addEventListener('scroll', handleScroll);
  handleScroll(); // вызвать сразу
  
  // Возвращаем функцию для отписки
  return () => window.removeEventListener('scroll', handleScroll);
}
