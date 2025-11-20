/**
 * navbarHeight.js
 * Устанавливает CSS-переменную --navbar-h с реальной высотой navbar
 * Обновляется при ресайзе окна
 * 
 * @module navbarHeight
 * @version 1.0.0
 */

/**
 * Инициализация отслеживания высоты navbar
 */
export function initNavbarHeight() {
  const nav = document.querySelector('.app-navbar');
  
  if (!nav) {
    console.log('navbarHeight: .app-navbar not found, skip');
    return null;
  }

  function updateHeight() {
    document.documentElement.style.setProperty('--navbar-h', nav.offsetHeight + 'px');
  }

  // Установить сразу
  updateHeight();

  // Обновлять при ресайзе
  window.addEventListener('resize', updateHeight);

  console.log('navbarHeight: initialized');

  return {
    update: updateHeight
  };
}
