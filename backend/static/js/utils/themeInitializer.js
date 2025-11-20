/**
 * @module themeInitializer
 * @description Немедленное применение темы в <head> для предотвращения "мигания" при загрузке.
 * Этот скрипт должен выполняться синхронно в <head> до загрузки body.
 * 
 * ВАЖНО: Это НЕ ES6 модуль, а обычный IIFE для использования в <head>.
 * 
 * Использование в шаблоне:
 * {% block extra_css %}
 * <script src="{% static 'js/utils/themeInitializer.js' %}"></script>
 * {% endblock %}
 */

(function() {
  'use strict';
  
  const root = document.documentElement;
  const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
  
  /**
   * Получает сохранённую тему из localStorage.
   * @returns {string} 'light', 'auto' или 'dark'
   */
  function getSavedTheme() {
    try {
      return localStorage.getItem('theme') || 'auto';
    } catch (e) {
      return 'auto';
    }
  }
  
  /**
   * Определяет эффективную тему на основе режима и системных настроек.
   * @param {string} mode - Режим темы ('light', 'auto', 'dark')
   * @returns {string} 'light' или 'dark'
   */
  function getEffectiveTheme(mode) {
    if (mode === 'auto') {
      return mediaQuery.matches ? 'dark' : 'light';
    }
    return mode;
  }
  
  /**
   * Применяет тему к документу.
   */
  function applyTheme() {
    const savedMode = getSavedTheme();
    const effectiveTheme = getEffectiveTheme(savedMode);
    root.setAttribute('data-bs-theme', effectiveTheme);
  }
  
  // Немедленное применение темы
  applyTheme();
  
  // Реагируем на изменение системной темы в режиме "авто"
  mediaQuery.addEventListener('change', function() {
    if (getSavedTheme() === 'auto') {
      applyTheme();
    }
  });
})();
