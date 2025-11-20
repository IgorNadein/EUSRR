/**
 * @module autoScrollerHandler
 * @description Автоматический горизонтальный скроллер для галереи элементов.
 * Поддерживает плавную непрерывную прокрутку, паузу при наведении, центрирование элемента.
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
 * initAutoScroller({ selector: '.js-join-scroller', speed: 0.5 });
 */

const DEFAULT_SPEED = 0.5; // пикселей за кадр (примерно 30px/сек при 60fps)
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
 * @param {number} [options.speed=0.5] - Скорость прокрутки в пикселях за кадр
 * @returns {Object} API с методами start, stop, destroy
 */
function initSingleScroller(wrapper, options = {}) {
  const { speed = DEFAULT_SPEED } = options;
  
  console.log('initSingleScroller: starting, speed =', speed);
  
  const rail = wrapper.querySelector('.join-rail');
  if (!rail) {
    console.warn('initAutoScroller: .join-rail не найден');
    return { start: () => {}, stop: () => {}, destroy: () => {} };
  }

  // Проверяем, нужен ли скролл (контент переполняет контейнер)
  const hasOverflow = rail.scrollWidth > wrapper.clientWidth + 4;
  console.log('initSingleScroller: hasOverflow =', hasOverflow, 'scrollWidth =', rail.scrollWidth, 'clientWidth =', wrapper.clientWidth);
  
  if (!hasOverflow) {
    console.log('initSingleScroller: no overflow, skipping');
    return { start: () => {}, stop: () => {}, destroy: () => {} };
  }

  // Дублируем элементы для бесшовного цикла
  const originalChildren = Array.from(rail.children);
  const clones = originalChildren.map(node => node.cloneNode(true));
  rail.append(...clones);
  
  console.log('initSingleScroller: cloned', originalChildren.length, 'items');

  // Пересчитываем overflow после клонирования
  const hasOverflowAfterClone = rail.scrollWidth > wrapper.clientWidth + 4;
  console.log('initSingleScroller: hasOverflowAfterClone =', hasOverflowAfterClone);
  
  if (!hasOverflowAfterClone) {
    // Удаляем клоны если даже с ними нет переполнения
    clones.forEach(clone => clone.remove());
    console.log('initSingleScroller: no overflow after clone, removing clones');
    return { start: () => {}, stop: () => {}, destroy: () => {} };
  }

  // Состояние
  let scrollStep = computeScrollStep(rail);
  const originalCount = originalChildren.length;
  let animationFrame = null;
  let paused = false;
  let resizeFrame = null;
  
  console.log('initSingleScroller: scrollStep =', scrollStep, 'originalCount =', originalCount);

  /**
   * Один кадр анимации - плавный скролл.
   */
  let frameCount = 0;
  let accumulatedScroll = 0; // Накопленные дробные пиксели
  
  function animate() {
    if (paused) {
      animationFrame = requestAnimationFrame(animate);
      return;
    }
    
    frameCount++;
    
    const maxScroll = scrollStep * originalCount;
    
    // Если достигли конца первой копии - прыгаем в начало
    if (wrapper.scrollLeft >= maxScroll - 2) {
      wrapper.scrollLeft = 0;
      accumulatedScroll = 0;
      console.log('animate: reset to start, maxScroll =', maxScroll);
    }
    
    // Накапливаем дробные пиксели
    accumulatedScroll += speed;
    
    // Скроллим только когда накопился хотя бы 1 пиксель
    if (accumulatedScroll >= 1) {
      const scrollAmount = Math.floor(accumulatedScroll);
      accumulatedScroll -= scrollAmount; // Оставляем дробную часть
      
      wrapper.scrollBy({
        left: scrollAmount,
        behavior: 'auto'
      });
      
      if (frameCount % 60 === 0) {
        console.log('animate: frame', frameCount, 'scrollLeft =', wrapper.scrollLeft, 'scrollAmount =', scrollAmount);
      }
    }
    
    animationFrame = requestAnimationFrame(animate);
  }

  /**
   * Запускает автоматическую прокрутку.
   */
  function start() {
    console.log('start: starting animation');
    if (!animationFrame) {
      animationFrame = requestAnimationFrame(animate);
    }
  }

  /**
   * Останавливает автоматическую прокрутку.
   */
  function stop() {
    if (animationFrame) {
      cancelAnimationFrame(animationFrame);
      animationFrame = null;
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
   * Обработчик нажатия кнопки мыши на элементе.
   */
  function handleItemMouseDown(event) {
    // Отменяем поведение по умолчанию чтобы не начиналось перетаскивание
    event.preventDefault();
    
    // Сразу снимаем паузу и убираем увеличение
    const item = event.currentTarget;
    paused = false;
    
    // Добавляем класс для отключения hover
    item.classList.add('no-hover');
    
    // Добавляем глобальный обработчик отпускания кнопки
    function handleGlobalMouseUp() {
      item.classList.remove('no-hover');
      document.removeEventListener('mouseup', handleGlobalMouseUp);
    }
    
    document.addEventListener('mouseup', handleGlobalMouseUp);
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
    item.addEventListener('mousedown', handleItemMouseDown);
    item.addEventListener('focusin', handleItemFocusIn);
    item.addEventListener('focusout', handleItemFocusOut);
  });

  // Глобальные обработчики
  window.addEventListener('resize', handleResize);
  document.addEventListener('visibilitychange', handleVisibilityChange);

  // Проверяем prefers-reduced-motion
  const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  console.log('initSingleScroller: prefersReducedMotion =', prefersReducedMotion);
  
  if (!prefersReducedMotion) {
    start();
  } else {
    console.log('initSingleScroller: skipping animation due to prefers-reduced-motion');
  }

  /**
   * Очистка всех обработчиков и таймеров.
   */
  function destroy() {
    stop();
    
    items.forEach(item => {
      item.removeEventListener('mouseenter', handleItemMouseEnter);
      item.removeEventListener('mouseleave', handleItemMouseLeave);
      item.removeEventListener('mousedown', handleItemMouseDown);
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
 * @param {number} [options.speed=0.5] - Скорость прокрутки в пикселях за кадр (примерно 30px/сек при 60fps)
 * @returns {Object} API с методом destroy
 */
export function initAutoScroller(options = {}) {
  const { selector = '.js-join-scroller', speed = DEFAULT_SPEED } = options;
  
  const scrollers = [];
  
  document.querySelectorAll(selector).forEach(wrapper => {
    const scroller = initSingleScroller(wrapper, { speed });
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
