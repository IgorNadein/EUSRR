/**
 * chatMenuActions.js
 * Обработчик действий меню чата (закрепить, уведомления, редактировать, удалить)
 */

export function initChatMenuActions() {
  
  // Обновление текста "Закрепить"/"Открепить" при открытии dropdown
  document.addEventListener('show.bs.dropdown', function(e) {
    const dropdownButton = e.target;
    const chatRow = dropdownButton.closest('.chat-row');
    if (!chatRow) return;

    const isPinned = chatRow.classList.contains('pinned');
    const dropdownMenu = dropdownButton.nextElementSibling;
    const pinTextElement = dropdownMenu?.querySelector('[data-pin-text]');
    
    if (pinTextElement) {
      pinTextElement.textContent = isPinned ? 'Открепить' : 'Закрепить';
    }
  });

  // Обработка кликов по пунктам меню
  document.addEventListener('click', function(e) {
    const actionLink = e.target.closest('[data-action]');
    if (!actionLink) return;

    e.preventDefault();
    e.stopPropagation();

    const action = actionLink.dataset.action;
    const chatRow = actionLink.closest('.chat-row');
    if (!chatRow) return;

    const chatId = chatRow.dataset.chatId;
    const chatName = chatRow.querySelector('[data-chat-name]')?.textContent || 'этот чат';

    // Закрываем dropdown после клика
    const dropdownMenu = actionLink.closest('.dropdown-menu');
    const dropdownButton = dropdownMenu?.previousElementSibling;
    if (dropdownButton) {
      const dropdownInstance = bootstrap.Dropdown.getInstance(dropdownButton);
      if (dropdownInstance) {
        dropdownInstance.hide();
      }
    }

    // Выполняем действие
    switch(action) {
      case 'pin':
        handlePinAction(chatId, chatName, chatRow);
        break;
      case 'notifications':
        handleNotificationsAction(chatId, chatName);
        break;
      case 'edit':
        handleEditAction(chatId, chatName);
        break;
      case 'delete':
        handleDeleteAction(chatId, chatName);
        break;
      default:
        console.warn('Unknown action:', action);
    }
  });
}

/**
 * Обработка закрепления/открепления чата
 */
function handlePinAction(chatId, chatName, chatRow) {
  const isPinned = chatRow.classList.contains('pinned');
  const actionText = isPinned ? 'открепления' : 'закрепления';
  
  showDevMessage(`Функция ${actionText} чата находится в разработке`, 'info');
  
  // TODO: Реализовать API endpoint для закрепления
  /*
  fetch(`/communications/api/chat/${chatId}/pin/`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-CSRFToken': getCsrfToken()
    },
    body: JSON.stringify({ pinned: !isPinned })
  })
  .then(response => response.json())
  .then(data => {
    if (data.ok) {
      if (data.pinned) {
        chatRow.classList.add('pinned');
        moveToPinnedSection(chatRow);
      } else {
        chatRow.classList.remove('pinned');
        moveToUnpinnedSection(chatRow);
      }
    }
  })
  .catch(error => console.error('Pin error:', error));
  */
}

/**
 * Обработка настройки уведомлений
 */
function handleNotificationsAction(chatId, chatName) {
  showDevMessage('Функция настройки уведомлений находится в разработке', 'info');
  
  // TODO: Реализовать API endpoint для управления уведомлениями
  /*
  fetch(`/communications/api/chat/${chatId}/notifications/`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-CSRFToken': getCsrfToken()
    },
    body: JSON.stringify({ enabled: false })
  })
  .then(response => response.json())
  .then(data => {
    if (data.ok) {
      console.log('Notifications updated');
    }
  });
  */
}

/**
 * Обработка редактирования чата
 */
function handleEditAction(chatId, chatName) {
  showDevMessage('Функция редактирования чата находится в разработке', 'info');
  
  // TODO: Создать страницу редактирования чата
  // window.location.href = `/communications/chats/${chatId}/edit/`;
}

/**
 * Обработка удаления чата
 */
function handleDeleteAction(chatId, chatName) {
  showDevMessage('Функция удаления чата находится в разработке', 'warning');
  
  // TODO: Реализовать API endpoint для удаления
  /*
  if (!confirm(`Вы уверены, что хотите удалить чат "${chatName}"? Это действие необратимо.`)) {
    return;
  }

  fetch(`/communications/api/chat/${chatId}/delete/`, {
    method: 'DELETE',
    headers: {
      'Content-Type': 'application/json',
      'X-CSRFToken': getCsrfToken()
    }
  })
  .then(response => response.json())
  .then(data => {
    if (data.ok) {
      const chatRow = document.querySelector(`[data-chat-id="${chatId}"]`);
      if (chatRow) {
        chatRow.style.transition = 'opacity 0.3s';
        chatRow.style.opacity = '0';
        setTimeout(() => chatRow.remove(), 300);
      }
    } else {
      alert('Ошибка при удалении чата: ' + (data.error || 'Неизвестная ошибка'));
    }
  })
  .catch(error => {
    console.error('Delete error:', error);
    alert('Ошибка при удалении чата');
  });
  */
}

/**
 * Показать сообщение о разработке функции
 */
function showDevMessage(message, type = 'info') {
  // Создаем toast уведомление
  const toastContainer = getOrCreateToastContainer();
  
  const toastId = `toast-${Date.now()}`;
  const iconClass = type === 'warning' ? 'bi-exclamation-triangle-fill' : 'bi-info-circle-fill';
  const bgClass = type === 'warning' ? 'bg-warning' : 'bg-info';
  
  const toastHtml = `
    <div id="${toastId}" class="toast align-items-center text-white ${bgClass} border-0" role="alert" aria-live="assertive" aria-atomic="true">
      <div class="d-flex">
        <div class="toast-body">
          <i class="${iconClass} me-2"></i>${message}
        </div>
        <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button>
      </div>
    </div>
  `;
  
  toastContainer.insertAdjacentHTML('beforeend', toastHtml);
  
  const toastElement = document.getElementById(toastId);
  const toast = new bootstrap.Toast(toastElement, {
    autohide: true,
    delay: 3000
  });
  
  toast.show();
  
  // Удаляем элемент после скрытия
  toastElement.addEventListener('hidden.bs.toast', () => {
    toastElement.remove();
  });
}

/**
 * Получить или создать контейнер для toast уведомлений
 */
function getOrCreateToastContainer() {
  let container = document.getElementById('chat-toast-container');
  
  if (!container) {
    container = document.createElement('div');
    container.id = 'chat-toast-container';
    container.className = 'toast-container position-fixed top-0 end-0 p-3';
    container.style.zIndex = '9999';
    document.body.appendChild(container);
  }
  
  return container;
}

/**
 * Получить CSRF токен
 */
function getCsrfToken() {
  const tokenInput = document.querySelector('[name=csrfmiddlewaretoken]');
  if (tokenInput) {
    return tokenInput.value;
  }
  
  const name = 'csrftoken';
  let cookieValue = null;
  if (document.cookie && document.cookie !== '') {
    const cookies = document.cookie.split(';');
    for (let i = 0; i < cookies.length; i++) {
      const cookie = cookies[i].trim();
      if (cookie.substring(0, name.length + 1) === (name + '=')) {
        cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
        break;
      }
    }
  }
  return cookieValue;
}

/**
 * Переместить чат в секцию закрепленных
 */
function moveToPinnedSection(chatRow) {
  const parent = chatRow.parentElement;
  const firstUnpinned = Array.from(parent.children).find(row => 
    !row.classList.contains('pinned')
  );
  
  if (firstUnpinned) {
    parent.insertBefore(chatRow, firstUnpinned);
  } else {
    parent.insertBefore(chatRow, parent.firstChild);
  }
}

/**
 * Переместить чат в секцию обычных
 */
function moveToUnpinnedSection(chatRow) {
  const parent = chatRow.parentElement;
  parent.appendChild(chatRow);
}
