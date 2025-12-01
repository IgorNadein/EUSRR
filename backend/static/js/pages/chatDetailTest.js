/**
 * Chat Detail Page - TEST VERSION
 * Минимальная версия для проверки загрузки
 */

console.log('[ChatDetailTest] ========== MODULE LOADED ==========');

document.addEventListener('DOMContentLoaded', () => {
  console.log('[ChatDetailTest] ========== DOM READY ==========');
  
  const appContainer = document.getElementById('chatDetailApp');
  console.log('[ChatDetailTest] App container:', appContainer);
  
  if (appContainer) {
    console.log('[ChatDetailTest] Data attributes:', appContainer.dataset);
  }
  
  // Простая привязка к кнопке
  const submitBtn = document.querySelector('.btn-send');
  console.log('[ChatDetailTest] Submit button:', submitBtn);
  
  if (submitBtn) {
    submitBtn.addEventListener('click', (e) => {
      console.log('[ChatDetailTest] BUTTON CLICKED!');
      e.preventDefault();
      alert('Button clicked! This works!');
    });
  }
});
