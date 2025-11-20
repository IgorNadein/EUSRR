/**
 * DOM Utilities
 * 
 * Утилиты для работы с DOM: показ/скрытие элементов, работа с классами и т.д.
 * 
 * Использование:
 * import { show, hide, toggle } from '{% static "js/utils/domUtils.js" %}';
 */

/**
 * Показывает элемент (удаляет класс d-none)
 * 
 * @param {HTMLElement|null} element - элемент для показа
 * @returns {boolean} - true если элемент был скрыт и теперь показан
 * 
 * @example
 * show(document.getElementById('myElement'));
 */
export function show(element) {
  if (!element) return false;
  const wasHidden = element.classList.contains('d-none');
  element.classList.remove('d-none');
  return wasHidden;
}

/**
 * Скрывает элемент (добавляет класс d-none)
 * 
 * @param {HTMLElement|null} element - элемент для скрытия
 * @returns {boolean} - true если элемент был виден и теперь скрыт
 * 
 * @example
 * hide(document.getElementById('myElement'));
 */
export function hide(element) {
  if (!element) return false;
  const wasVisible = !element.classList.contains('d-none');
  element.classList.add('d-none');
  return wasVisible;
}

/**
 * Переключает видимость элемента (toggle класс d-none)
 * 
 * @param {HTMLElement|null} element - элемент для переключения
 * @param {boolean} [force] - принудительно показать (true) или скрыть (false)
 * @returns {boolean} - true если элемент теперь виден, false если скрыт
 * 
 * @example
 * toggle(document.getElementById('myElement'));
 * toggle(document.getElementById('myElement'), true); // принудительно показать
 */
export function toggle(element, force) {
  if (!element) return false;
  
  if (force !== undefined) {
    element.classList.toggle('d-none', !force);
    return force;
  }
  
  element.classList.toggle('d-none');
  return !element.classList.contains('d-none');
}

/**
 * Проверяет, виден ли элемент (нет класса d-none)
 * 
 * @param {HTMLElement|null} element - элемент для проверки
 * @returns {boolean} - true если элемент виден
 * 
 * @example
 * if (isVisible(document.getElementById('myElement'))) {
 *   console.log('Элемент виден');
 * }
 */
export function isVisible(element) {
  if (!element) return false;
  return !element.classList.contains('d-none');
}

/**
 * Показывает элемент с временной задержкой перед скрытием
 * Полезно для временных уведомлений
 * 
 * @param {HTMLElement|null} element - элемент для показа
 * @param {number} [duration=4000] - длительность показа в миллисекундах
 * @returns {number|null} - ID таймера для возможной отмены через clearTimeout
 * 
 * @example
 * const timerId = showTemporary(alertElement, 3000);
 * // Отменить автоскрытие: clearTimeout(timerId);
 */
export function showTemporary(element, duration = 4000) {
  if (!element) return null;
  
  show(element);
  return setTimeout(() => hide(element), duration);
}

/**
 * Добавляет/удаляет класс CSS у элемента
 * 
 * @param {HTMLElement|null} element - элемент
 * @param {string} className - имя класса
 * @param {boolean} add - true = добавить, false = удалить
 * 
 * @example
 * setClass(element, 'active', true); // добавить класс active
 * setClass(element, 'disabled', false); // удалить класс disabled
 */
export function setClass(element, className, add) {
  if (!element) return;
  
  if (add) {
    element.classList.add(className);
  } else {
    element.classList.remove(className);
  }
}

/**
 * Находит ближайший родительский элемент с указанным селектором
 * Аналог element.closest(), но с дополнительными проверками
 * 
 * @param {HTMLElement|null} element - начальный элемент
 * @param {string} selector - CSS селектор
 * @returns {HTMLElement|null} - найденный элемент или null
 * 
 * @example
 * const row = closest(button, '.chat-row');
 */
export function closest(element, selector) {
  if (!element) return null;
  return element.closest(selector);
}

/**
 * Безопасно получает элемент по ID
 * 
 * @param {string} id - ID элемента
 * @returns {HTMLElement|null} - элемент или null
 * 
 * @example
 * const el = getById('myElement');
 */
export function getById(id) {
  return document.getElementById(id);
}

/**
 * Безопасно получает первый элемент по селектору
 * 
 * @param {string} selector - CSS селектор
 * @param {HTMLElement|Document} [context=document] - контекст поиска
 * @returns {HTMLElement|null} - элемент или null
 * 
 * @example
 * const el = querySelector('.my-class');
 * const child = querySelector('.child', parentElement);
 */
export function querySelector(selector, context = document) {
  if (!context) return null;
  return context.querySelector(selector);
}

/**
 * Безопасно получает все элементы по селектору
 * 
 * @param {string} selector - CSS селектор
 * @param {HTMLElement|Document} [context=document] - контекст поиска
 * @returns {HTMLElement[]} - массив элементов
 * 
 * @example
 * const items = querySelectorAll('.item');
 * items.forEach(item => console.log(item));
 */
export function querySelectorAll(selector, context = document) {
  if (!context) return [];
  return Array.from(context.querySelectorAll(selector));
}
