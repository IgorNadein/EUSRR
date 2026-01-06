/**
 * @module logoutModalHandler
 * @description Обработчик модального окна выхода из системы.
 * Управляет UX: ESC/Enter/клик по фону для отмены, автофокус на кнопке.
 * 
 * Пример HTML:
 * <div class="ios-overlay">
 *   <form method="post">
 *     <button type="submit" id="confirmBtn">Выйти</button>
 *     <a href="#" id="cancelBtn">Отмена</a>
 *   </form>
 * </div>
 * 
 * Использование:
 * import { initLogoutModal } from './logoutModalHandler.js';
 * initLogoutModal({
 *   cancelUrl: '/dashboard/',
 *   loginUrl: '/login/'
 * });
 */

/**
 * Инициализирует обработчик модального окна выхода.
 * @param {Object} options - Опции инициализации
 * @param {string} [options.cancelButtonId='cancelBtn'] - ID кнопки отмены
 * @param {string} [options.confirmButtonId='confirmBtn'] - ID кнопки подтверждения
 * @param {string} [options.overlaySelector='.ios-overlay'] - Селектор оверлея
 * @param {string} options.loginUrl - URL страницы входа (fallback)
 * @param {string} [options.cancelUrl] - URL для перехода при отмене
 * @returns {Object} API с методом destroy
 */
export function initLogoutModal(options) {
  const {
    cancelButtonId = 'cancelBtn',
    confirmButtonId = 'confirmBtn',
    overlaySelector = '.ios-overlay',
    loginUrl,
    cancelUrl
  } = options;

  const cancelButton = document.getElementById(cancelButtonId);
  const confirmButton = document.getElementById(confirmButtonId);
  const overlay = document.querySelector(overlaySelector);

  if (!cancelButton || !confirmButton || !overlay) {
    console.warn('initLogoutModal: обязательные элементы не найдены');
    return { destroy: () => {} };
  }

  /**
   * Отписывается от push-уведомлений перед выходом
   */
  async function unsubscribeFromPush() {
    if (window.pushNotifications && typeof window.pushNotifications.unsubscribe === 'function') {
      try {
        await window.pushNotifications.unsubscribe();
        console.log('[Logout] Push подписка удалена');
      } catch (error) {
        console.error('[Logout] Ошибка отписки:', error);
      }
    }
    // Очищаем localStorage
    localStorage.removeItem('push_endpoint');
  }

  /**
   * Обработчик отправки формы logout
   */
  function handleLogoutSubmit(event) {
    // Не preventDefault - позволяем форме отправиться
    // Но сначала отписываемся асинхронно
    unsubscribeFromPush().catch(err => {
      console.error('[Logout] Unsubscribe error:', err);
    });
  }

  /**
   * Возврат на предыдущую страницу или указанный URL.
   */
  function goBack() {
    // Проверяем параметр ?next= в URL
    const params = new URLSearchParams(location.search);
    const next = (params.get('next') || '').trim();
    
    if (next) {
      location.href = next;
      return;
    }

    // Если передан cancelUrl
    if (cancelUrl) {
      location.href = cancelUrl;
      return;
    }

    // Если есть referrer - возвращаемся назад
    if (document.referrer) {
      history.back();
      return;
    }

    // Fallback - переход на страницу входа
    location.href = loginUrl;
  }

  /**
   * Обработчик клика по кнопке отмены.
   * @param {Event} event - Событие клика
   */
  function handleCancelClick(event) {
    event.preventDefault();
    goBack();
  }

  /**
   * Обработчик клика по оверлею.
   * @param {Event} event - Событие клика
   */
  function handleOverlayClick(event) {
    // Закрываем только если кликнули по самому оверлею, а не по содержимому
    if (event.target === overlay) {
      goBack();
    }
  }

  /**
   * Обработчик нажатия клавиш.
   * @param {KeyboardEvent} event - Событие клавиатуры
   */
  function handleKeyDown(event) {
    if (event.key === 'Escape') {
      event.preventDefault();
      goBack();
    }
    
    // Enter работает нативно для submit кнопки, но не для cancel
    if (event.key === 'Enter' && document.activeElement === cancelButton) {
      event.preventDefault();
      goBack();
    }
  }

  // Установка обработчиков
  cancelButton.addEventListener('click', handleCancelClick);
  overlay.addEventListener('click', handleOverlayClick);
  window.addEventListener('keydown', handleKeyDown);
  
  // Добавляем обработчик на форму logout
  const logoutForm = confirmButton.closest('form');
  if (logoutForm) {
    logoutForm.addEventListener('submit', handleLogoutSubmit);
  }

  // Автофокус на кнопке подтверждения после небольшой задержки
  setTimeout(() => {
    confirmButton?.focus();
  }, 10);

  /**
   * Функция для удаления всех обработчиков.
   */
  function destroy() {
    cancelButton.removeEventListener('click', handleCancelClick);
    overlay.removeEventListener('click', handleOverlayClick);
    window.removeEventListener('keydown', handleKeyDown);
  }

  return { destroy };
}

// Экспорт для совместимости с неModular кодом
if (typeof window !== 'undefined') {
  window.initLogoutModal = initLogoutModal;
}
