/**
 * Bottom Navigation Bar
 * Управление нижней панелью навигации для мобильных устройств
 */

document.addEventListener('DOMContentLoaded', function() {
  // Кнопка уведомлений в нижней панели
  const bottomNotificationToggle = document.getElementById('bottomNotificationToggle');
  const notificationDropdown = document.getElementById('notificationDropdown');
  const notificationBadge = document.getElementById('notificationBadge');
  const bottomNotificationBadge = document.getElementById('bottomNotificationBadge');

  // Синхронизация бейджей между верхней и нижней панелью
  function syncNotificationBadges() {
    if (notificationBadge && bottomNotificationBadge) {
      const count = notificationBadge.textContent;
      const isVisible = notificationBadge.style.display !== 'none';
      
      bottomNotificationBadge.textContent = count;
      if (isVisible && count !== '0') {
        bottomNotificationBadge.style.display = '';
        bottomNotificationBadge.classList.add('pulse');
        setTimeout(() => bottomNotificationBadge.classList.remove('pulse'), 600);
      } else {
        bottomNotificationBadge.style.display = 'none';
      }
    }
  }

  // Наблюдатель за изменениями бейджа уведомлений
  if (notificationBadge) {
    const observer = new MutationObserver(syncNotificationBadges);
    observer.observe(notificationBadge, {
      attributes: true,
      childList: true,
      characterData: true,
      subtree: true
    });
    // Первоначальная синхронизация
    syncNotificationBadges();
  }

  // Открытие уведомлений из нижней панели
  if (bottomNotificationToggle && notificationDropdown) {
    bottomNotificationToggle.addEventListener('click', function(e) {
      e.preventDefault();
      e.stopPropagation();
      
      const isVisible = notificationDropdown.style.display !== 'none';
      
      if (isVisible) {
        notificationDropdown.style.display = 'none';
      } else {
        notificationDropdown.style.display = 'block';
        // Позиционируем над нижней панелью
        notificationDropdown.style.bottom = '70px';
        notificationDropdown.style.right = '10px';
        notificationDropdown.style.top = 'auto';
        notificationDropdown.style.left = 'auto';
      }
    });
  }

  // Кнопка поиска в нижней панели
  const bottomSearchToggle = document.getElementById('bottomSearchToggle');
  
  if (bottomSearchToggle) {
    bottomSearchToggle.addEventListener('click', function(e) {
      e.preventDefault();
      // Перенаправляем на страницу поиска
      window.location.href = '/search/';
    });
  }

  // Закрытие выпадающих элементов при клике вне их
  document.addEventListener('click', function(e) {
    if (notificationDropdown && 
        !notificationDropdown.contains(e.target) && 
        !bottomNotificationToggle?.contains(e.target)) {
      notificationDropdown.style.display = 'none';
    }
  });
});
