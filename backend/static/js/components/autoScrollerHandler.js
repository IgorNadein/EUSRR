/**
 * @module autoScrollerHandler
 * @description Автоматический горизонтальный скроллер для галереи элементов.
 * Поддерживает бесконечный цикл, паузу при наведении, центрирование элемента.
 * 
 * Пример HTML:
 * <div class="js-join-scroller overflow-hidden">
 *   <div class="join-rail d-flex gap-3">
 *     <div class="join-item">...</div>
 *     <div class="join-item">...</div>
 *   </div>
 * </div>
 * 
 * Использование:
 * import { initAutoScroller } from './autoScrollerHandler.js';
 * initAutoScroller({ selector: '.js-join-scroller' });
 */

const DEFAULT_STEP_MS = 3000;
const SCROLL_BEHAVIOR = 'smooth';

/**
 * Центрирует элемент в видимой области контейнера.
 * @param {HTMLElement} container - Контейнер со скроллом
 * @param {HTMLElement} item - Элемент для центрирования
 */
function centerItemInView(container, item) {
  const itemRect = item.getBoundingClientRect();
  const containerRect = container.getBoundingClientRect();
  
  const itemCenter = itemRect.left + itemRect.width / 2;
  const containerCenter = containerRect.left + containerRect.width / 2;
  const delta = itemCenter - containerCenter;
  
  container.scrollTo({
    left: container.scrollLeft + delta,
    behavior: SCROLL_BEHAVIOR
  });
}

/**
 * Вычисляет шаг скролла (ширина элемента + gap).
 * @param {HTMLElement} rail - Элемент с flex-контейнером
 * @returns {number} Размер шага в пикселях
 */
function computeScrollStep(rail) {
  const firstChild = rail.firstElementChild;
  if (!firstChild) return 0;
  
  const rect = firstChild.getBoundingClientRect();
  const gap = parseFloat(getComputedStyle(rail).gap || '0') || 0;
  
  return Math.round(rect.width + gap);
}

/**
 * Инициализирует автоскроллер для одного контейнера.
 * @param {HTMLElement} wrapper - Обёртка со скроллом
 * @param {Object} options - Опции
 * @param {number} [options.stepMs=3000] - Интервал между прокрутками в миллисекундах
 * @returns {Object} API с методами start, stop, destroy
 */
function initSingleScroller(wrapper, options = {}) {
  const { stepMs = DEFAULT_STEP_MS } = options;
  
  const rail = wrapper.querySelector('.join-rail');
  if (!rail) {
    console.warn('initAutoScroller: .join-rail не найден');
    return { start: () => {}, stop: () => {}, destroy: () => {} };
  }

  // Проверяем, нужен ли скролл (контент переполняет контейнер)
  const hasOverflow = rail.scrollWidth > wrapper.clientWidth + 4;
  if (!hasOverflow) {
    return { start: () => {}, stop: () => {}, destroy: () => {} };
  }

  // Дублируем элементы для бесшовного цикла
  const originalChildren = Array.from(rail.children);
  const clones = originalChildren.map(node => node.cloneNode(true));
  rail.append(...clones);

  // Состояние
  let scrollStep = computeScrollStep(rail);
  const originalCount = originalChildren.length;
  let timer = null;
  let paused = false;
  let resizeFrame = null;

  /**
   * Один шаг скролла.
   */
  function tick() {
    if (paused) return;
    
    const maxScroll = scrollStep * originalCount;
    
    // Если достигли конца первой копии - прыгаем в начало
    if (wrapper.scrollLeft >= maxScroll - 2) {
      wrapper.scrollLeft = 0;
    }
    
    wrapper.scrollBy({
      left: scrollStep,
      behavior: SCROLL_BEHAVIOR
    });
  }

  /**
   * Запускает автоматическую прокрутку.
   */
  function start() {
    if (!timer) {
      timer = setInterval(tick, stepMs);
    }
  }

  /**
   * Останавливает автоматическую прокрутку.
   */
  function stop() {
    if (timer) {
      clearInterval(timer);
      timer = null;
    }
  }

  /**
   * Обработчик наведения на элемент.
   */
  function handleItemMouseEnter(event) {
    paused = true;
    centerItemInView(wrapper, event.currentTarget);
  }

  /**
   * Обработчик ухода курсора с элемента.
   */
  function handleItemMouseLeave() {
    paused = false;
  }

  /**
   * Обработчик получения фокуса элементом.
   */
  function handleItemFocusIn(event) {
    paused = true;
    centerItemInView(wrapper, event.currentTarget);
  }

  /**
   * Обработчик потери фокуса элементом.
   */
  function handleItemFocusOut() {
    paused = false;
  }

  /**
   * Обработчик изменения размера окна.
   */
  function handleResize() {
    cancelAnimationFrame(resizeFrame);
    resizeFrame = requestAnimationFrame(() => {
      scrollStep = computeScrollStep(rail);
    });
  }

  /**
   * Обработчик изменения видимости вкладки.
   */
  function handleVisibilityChange() {
    if (document.hidden) {
      stop();
    } else {
      start();
    }
  }

  // Устанавливаем обработчики на все элементы
  const items = rail.querySelectorAll('.join-item');
  items.forEach(item => {
    item.addEventListener('mouseenter', handleItemMouseEnter);
    item.addEventListener('mouseleave', handleItemMouseLeave);
    item.addEventListener('focusin', handleItemFocusIn);
    item.addEventListener('focusout', handleItemFocusOut);
  });

  // Глобальные обработчики
  window.addEventListener('resize', handleResize);
  document.addEventListener('visibilitychange', handleVisibilityChange);

  // Проверяем prefers-reduced-motion
  const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  if (!prefersReducedMotion) {
    start();
  }

  /**
   * Очистка всех обработчиков и таймеров.
   */
  function destroy() {
    stop();
    
    items.forEach(item => {
      item.removeEventListener('mouseenter', handleItemMouseEnter);
      item.removeEventListener('mouseleave', handleItemMouseLeave);
      item.removeEventListener('focusin', handleItemFocusIn);
      item.removeEventListener('focusout', handleItemFocusOut);
    });
    
    window.removeEventListener('resize', handleResize);
    document.removeEventListener('visibilitychange', handleVisibilityChange);
    cancelAnimationFrame(resizeFrame);
    
    // Удаляем клонированные элементы
    clones.forEach(clone => clone.remove());
  }

  return { start, stop, destroy };
}

/**
 * Инициализирует автоскроллеры для всех элементов по селектору.
 * @param {Object} options - Опции
 * @param {string} [options.selector='.js-join-scroller'] - CSS-селектор контейнеров
 * @param {number} [options.stepMs=3000] - Интервал между прокрутками в миллисекундах
 * @returns {Object} API с методом destroy
 */
export function initAutoScroller(options = {}) {
  const { selector = '.js-join-scroller', stepMs = DEFAULT_STEP_MS } = options;
  
  const scrollers = [];
  
  document.querySelectorAll(selector).forEach(wrapper => {
    const scroller = initSingleScroller(wrapper, { stepMs });
    scrollers.push(scroller);
  });

  /**
   * Останавливает и очищает все скроллеры.
   */
  function destroy() {
    scrollers.forEach(scroller => scroller.destroy());
    scrollers.length = 0;
  }

  return { destroy };
}

// Экспорт для совместимости с неModular кодом
if (typeof window !== 'undefined') {
  window.initAutoScroller = initAutoScroller;
}
