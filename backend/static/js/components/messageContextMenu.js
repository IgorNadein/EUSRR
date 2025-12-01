// backend/static/js/components/messageContextMenu.js
/**
 * Контекстное меню для сообщений (как в Telegram/WhatsApp)
 * - Мобилка: долгое нажатие
 * - Десктоп: правый клик
 */

export class MessageContextMenu {
    constructor(config = {}) {
        console.log('[MessageContextMenu] Constructor called', config);
        
        this.onReactionSelect = config.onReactionSelect || (() => {});
        this.emojis = config.emojis || ['👍', '❤️', '😂', '😮', '😢', '🙏', '👏', '🔥'];
        this.currentUserId = config.currentUserId;
        this.containerId = config.containerId || 'chatScroll';
        
        this.activeMenu = null;
        this.highlightedMessage = null; // Храним ссылку на подсвеченное сообщение
        this.longPressTimer = null;
        this.longPressDuration = 500; // 500ms для долгого нажатия
        
        this.init();
        this.attachToExistingMessages();
        this.observeNewMessages();
    }

    init() {
        // Закрытие меню при клике вне его
        document.addEventListener('click', (e) => {
            if (this.activeMenu && !e.target.closest('.message-context-menu')) {
                this.removeHighlight(); // Убираем подсветку
                this.closeMenu();
            }
        });

        // Закрытие при Escape
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && this.activeMenu) {
                this.removeHighlight(); // Убираем подсветку
                this.closeMenu();
            }
        });

        // Закрытие при скролле
        document.addEventListener('scroll', () => {
            if (this.activeMenu) {
                this.removeHighlight(); // Убираем подсветку
                this.closeMenu();
            }
        }, true);
    }

    /**
     * Подключить контекстное меню ко всем существующим сообщениям
     */
    attachToExistingMessages() {
        console.log('[MessageContextMenu] Attaching to existing messages in:', this.containerId);
        const container = document.getElementById(this.containerId);
        
        if (!container) {
            console.warn('[MessageContextMenu] Container not found:', this.containerId);
            return;
        }
        
        const messages = container.querySelectorAll('.msg[data-message-id]');
        console.log('[MessageContextMenu] Found', messages.length, 'messages');
        
        messages.forEach((msg) => {
            if (!msg.dataset.contextMenuAttached) {
                this.attachToMessage(msg);
                msg.dataset.contextMenuAttached = 'true';
            }
        });
    }

    /**
     * Наблюдать за новыми сообщениями через MutationObserver
     */
    observeNewMessages() {
        const container = document.getElementById(this.containerId);
        
        if (!container) {
            console.warn('[MessageContextMenu] Container not found for observer:', this.containerId);
            return;
        }
        
        console.log('[MessageContextMenu] Setting up MutationObserver');
        
        const observer = new MutationObserver((mutations) => {
            mutations.forEach((mutation) => {
                mutation.addedNodes.forEach((node) => {
                    if (node.nodeType === Node.ELEMENT_NODE) {
                        // Если добавлено само сообщение
                        if (node.classList?.contains('msg') && node.dataset.messageId) {
                            if (!node.dataset.contextMenuAttached) {
                                console.log('[MessageContextMenu] New message detected:', node.dataset.messageId);
                                this.attachToMessage(node);
                                node.dataset.contextMenuAttached = 'true';
                            }
                        }
                        
                        // Если добавлен контейнер с сообщениями
                        const newMessages = node.querySelectorAll?.('.msg[data-message-id]');
                        if (newMessages) {
                            newMessages.forEach((msg) => {
                                if (!msg.dataset.contextMenuAttached) {
                                    console.log('[MessageContextMenu] New message in batch:', msg.dataset.messageId);
                                    this.attachToMessage(msg);
                                    msg.dataset.contextMenuAttached = 'true';
                                }
                            });
                        }
                    }
                });
            });
        });
        
        observer.observe(container, {
            childList: true,
            subtree: true
        });
        
        this.observer = observer;
    }

    /**
     * Подключить обработчики к сообщению
     */
    attachToMessage(messageElement) {
        const messageId = messageElement.dataset.messageId;
        const authorId = parseInt(messageElement.dataset.authorId);
        const isOwn = authorId === this.currentUserId;
        
        console.log('[MessageContextMenu] attachToMessage called:', {
            messageId,
            authorId,
            currentUserId: this.currentUserId,
            isOwn,
            alreadyAttached: messageElement.dataset.contextMenuAttached
        });

        // Десктоп: правый клик
        messageElement.addEventListener('contextmenu', (e) => {
            console.log('[MessageContextMenu] *** CONTEXTMENU EVENT FIRED ***');
            console.log('[MessageContextMenu] Event details:', {
                clientX: e.clientX,
                clientY: e.clientY,
                target: e.target.tagName,
                messageId
            });
            e.preventDefault();
            this.showMenu(messageElement, messageId, isOwn, e.clientX, e.clientY);
        });
        
        console.log('[MessageContextMenu] Contextmenu listener attached to message:', messageId);

        // Мобилка: долгое нажатие
        let touchStartX, touchStartY;
        
        messageElement.addEventListener('touchstart', (e) => {
            console.log('[MessageContextMenu] Touchstart event on message:', messageId);
            touchStartX = e.touches[0].clientX;
            touchStartY = e.touches[0].clientY;
            
            this.longPressTimer = setTimeout(() => {
                console.log('[MessageContextMenu] Long press triggered on message:', messageId);
                // Вибрация для тактильной обратной связи
                if (navigator.vibrate) {
                    navigator.vibrate(50);
                }
                this.showMenu(messageElement, messageId, isOwn, touchStartX, touchStartY);
            }, this.longPressDuration);
        }, { passive: true });

        messageElement.addEventListener('touchmove', (e) => {
            // Отменяем долгое нажатие если палец двигается
            const touch = e.touches[0];
            const moveX = Math.abs(touch.clientX - touchStartX);
            const moveY = Math.abs(touch.clientY - touchStartY);
            
            if (moveX > 10 || moveY > 10) {
                console.log('[MessageContextMenu] Touch moved, cancelling long press');
                clearTimeout(this.longPressTimer);
            }
        }, { passive: true });

        messageElement.addEventListener('touchend', () => {
            console.log('[MessageContextMenu] Touch ended');
            clearTimeout(this.longPressTimer);
        }, { passive: true });

        messageElement.addEventListener('touchcancel', () => {
            console.log('[MessageContextMenu] Touch cancelled');
            clearTimeout(this.longPressTimer);
        }, { passive: true });
        
        console.log('[MessageContextMenu] All event listeners attached to message:', messageId);
    }

    /**
     * Показать контекстное меню
     */
    showMenu(messageElement, messageId, isOwn, x, y) {
        console.log('[MessageContextMenu] showMenu called:', {
            messageId,
            isOwn,
            x,
            y,
            messageElement: messageElement?.tagName
        });
        
        // Убрать подсветку с предыдущего сообщения (если было)
        this.removeHighlight();
        
        // Закрыть предыдущее меню
        this.closeMenu();

        // Создать меню
        console.log('[MessageContextMenu] Creating menu...');
        const menu = this.createMenu(messageElement, messageId, isOwn);
        console.log('[MessageContextMenu] Menu created, appending to body');
        document.body.appendChild(menu);
        this.activeMenu = menu;
        console.log('[MessageContextMenu] Menu appended to DOM');

        // Добавить подсветку НОВОГО сообщения
        console.log('[MessageContextMenu] Adding highlight to message');
        messageElement.classList.add('message-highlighted');
        this.highlightedMessage = messageElement; // Сохраняем ссылку

        // Позиционировать меню
        console.log('[MessageContextMenu] Positioning menu');
        this.positionMenu(menu, x, y);

        // Анимация появления
        requestAnimationFrame(() => {
            console.log('[MessageContextMenu] Adding show class for animation');
            menu.classList.add('show');
        });
    }

    /**
     * Создать HTML меню
     */
    createMenu(messageElement, messageId, isOwn) {
        console.log('[MessageContextMenu] createMenu:', { messageId, isOwn });
        
        const menu = document.createElement('div');
        menu.className = 'message-context-menu';
        menu.dataset.messageId = messageId;
        console.log('[MessageContextMenu] Menu element created with class:', menu.className);

        // Секция быстрых реакций
        console.log('[MessageContextMenu] Creating reactions HTML with', this.emojis.length, 'emojis');
        const reactionsHtml = this.emojis.map(emoji => `
            <button class="quick-reaction-btn" data-emoji="${emoji}" data-action="react">
                ${emoji}
            </button>
        `).join('');

        // Секция действий
        const actionsHtml = `
            <div class="menu-actions">
                <button class="menu-action" data-action="reply">
                    <i class="bi bi-reply"></i>
                    <span>Ответить</span>
                </button>
                ${isOwn ? `
                    <button class="menu-action" data-action="edit">
                        <i class="bi bi-pencil"></i>
                        <span>Редактировать</span>
                    </button>
                ` : ''}
                <button class="menu-action" data-action="forward">
                    <i class="bi bi-share"></i>
                    <span>Переслать</span>
                </button>
                <button class="menu-action" data-action="copy">
                    <i class="bi bi-clipboard"></i>
                    <span>Копировать</span>
                </button>
                <button class="menu-action" data-action="select">
                    <i class="bi bi-check-square"></i>
                    <span>Выбрать</span>
                </button>
                ${isOwn ? `
                    <button class="menu-action menu-action-danger" data-action="delete">
                        <i class="bi bi-trash"></i>
                        <span>Удалить</span>
                    </button>
                ` : ''}
            </div>
        `;

        console.log('[MessageContextMenu] Setting innerHTML...');
        menu.innerHTML = `
            <div class="quick-reactions">
                ${reactionsHtml}
            </div>
            ${actionsHtml}
        `;
        console.log('[MessageContextMenu] innerHTML set successfully');

        // Обработчики
        console.log('[MessageContextMenu] Attaching click handler to menu');
        menu.addEventListener('click', (e) => {
            const btn = e.target.closest('[data-action]');
            if (!btn) {
                console.log('[MessageContextMenu] Click outside action button');
                return;
            }

            e.preventDefault();
            e.stopPropagation();

            const action = btn.dataset.action;
            const emoji = btn.dataset.emoji;
            console.log('[MessageContextMenu] Action button clicked:', action, emoji);

            this.handleAction(action, messageElement, messageId, emoji);
            this.removeHighlight(); // Убираем подсветку при выборе действия
            this.closeMenu();
        });

        console.log('[MessageContextMenu] Menu fully constructed');
        return menu;
    }

    /**
     * Позиционировать меню на экране
     */
    positionMenu(menu, x, y) {
        console.log('[MessageContextMenu] positionMenu called:', { x, y });
        
        const menuRect = menu.getBoundingClientRect();
        const viewportWidth = window.innerWidth;
        const viewportHeight = window.innerHeight;
        
        console.log('[MessageContextMenu] Menu dimensions:', {
            width: menuRect.width,
            height: menuRect.height,
            viewportWidth,
            viewportHeight
        });

        let left = x;
        let top = y;

        // Не выходим за правый край
        if (left + menuRect.width > viewportWidth) {
            left = viewportWidth - menuRect.width - 10;
            console.log('[MessageContextMenu] Adjusted left to prevent overflow:', left);
        }

        // Не выходим за левый край
        if (left < 10) {
            left = 10;
            console.log('[MessageContextMenu] Adjusted left to prevent underflow:', left);
        }

        // Не выходим за нижний край
        if (top + menuRect.height > viewportHeight) {
            top = y - menuRect.height;
            console.log('[MessageContextMenu] Adjusted top to prevent bottom overflow:', top);
        }

        // Не выходим за верхний край
        if (top < 10) {
            top = 10;
            console.log('[MessageContextMenu] Adjusted top to prevent top overflow:', top);
        }

        console.log('[MessageContextMenu] Final position:', { left, top });
        menu.style.left = `${left}px`;
        menu.style.top = `${top}px`;
    }

    /**
     * Обработать действие
     */
    handleAction(action, messageElement, messageId, emoji) {
        console.log('[ContextMenu] Action:', action, 'Message:', messageId);
        
        switch (action) {
            case 'react':
                this.handleReact(messageId, emoji);
                break;
            case 'reply':
                this.handleReply(messageElement);
                break;
            case 'edit':
                this.handleEdit(messageElement);
                break;
            case 'delete':
                this.handleDelete(messageId);
                break;
            case 'forward':
                this.handleForward(messageId);
                break;
            case 'copy':
                this.handleCopy(messageElement);
                break;
            case 'select':
                this.handleSelect(messageElement, messageId);
                break;
        }
    }

    /**
     * Добавить реакцию
     */
    async handleReact(messageId, emoji) {
        console.log('[ContextMenu] Adding reaction:', emoji, 'to message:', messageId);
        try {
            await this.onReactionSelect(messageId, emoji);
        } catch (error) {
            console.error('[ContextMenu] Failed to add reaction:', error);
            this.showToast('Не удалось добавить реакцию');
        }
    }

    /**
     * Ответить на сообщение
     */
    handleReply(messageElement) {
        console.log('[MessageContextMenu] handleReply called');
        
        const bubble = messageElement.querySelector('.bubble');
        if (!bubble) {
            console.warn('[MessageContextMenu] Bubble not found in message element');
            return;
        }

        // Получаем данные сообщения
        const messageText = bubble.textContent.trim();
        const authorName = messageElement.querySelector('.small.text-secondary')?.textContent.split('·')[0]?.trim() || 'Пользователь';
        const messageId = messageElement.dataset.messageId;
        
        console.log('[MessageContextMenu] Reply data:', {
            messageId,
            authorName,
            messageTextLength: messageText.length
        });

        // Используем chatFormManager если доступен
        if (window.chatFormManager) {
            console.log('[MessageContextMenu] Using chatFormManager.setModeToReply');
            window.chatFormManager.setModeToReply(messageId, authorName, messageText);
        } else {
            console.warn('[MessageContextMenu] chatFormManager not available, using fallback');
            // Фоллбэк на старую логику (на случай если модуль не загружен)
            const textarea = document.querySelector('#id_content');
            if (textarea) {
                textarea.focus();
                this.showToast(`Ответ на сообщение от ${authorName}`);
            } else {
                console.error('[MessageContextMenu] Textarea #id_content not found');
            }
        }
    }

    /**
     * Редактировать сообщение
     */
    handleEdit(messageElement) {
        console.log('[MessageContextMenu] handleEdit called');
        
        const bubble = messageElement.querySelector('.bubble');
        if (!bubble) {
            console.warn('[MessageContextMenu] Bubble not found in message element');
            return;
        }

        // Получаем текст сообщения (без вложений и других элементов)
        let messageText = '';
        bubble.childNodes.forEach(node => {
            if (node.nodeType === Node.TEXT_NODE) {
                messageText += node.textContent;
            } else if (node.nodeName === 'BR') {
                messageText += '\n';
            }
        });

        const messageId = messageElement.dataset.messageId;
        
        console.log('[MessageContextMenu] Edit data:', {
            messageId,
            messageTextLength: messageText.length
        });

        // Используем chatFormManager если доступен
        if (window.chatFormManager) {
            console.log('[MessageContextMenu] Using chatFormManager.setModeToEdit');
            window.chatFormManager.setModeToEdit(messageId, messageText.trim());
        } else {
            console.warn('[MessageContextMenu] chatFormManager not available, using fallback');
            // Фоллбэк на старую логику
            const textarea = document.querySelector('#id_content');
            if (textarea) {
                textarea.value = messageText.trim();
                textarea.focus();
                this.showToast('Редактирование сообщения');
            } else {
                console.error('[MessageContextMenu] Textarea #id_content not found');
            }
        }
    }

    /**
     * Удалить сообщение
     */
    async handleDelete(messageId) {
        console.log('[MessageContextMenu] handleDelete called:', messageId);
        
        if (!confirm('Удалить это сообщение?')) {
            console.log('[MessageContextMenu] Delete cancelled by user');
            return;
        }

        try {
            const csrfToken = this.getCsrfToken();
            const url = `/api/v1/communications/messages/${messageId}/delete/`;
            
            console.log('[MessageContextMenu] Sending DELETE request to:', url);
            console.log('[MessageContextMenu] CSRF token:', csrfToken ? 'present' : 'missing');
            
            const response = await fetch(url, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken
                }
            });

            console.log('[MessageContextMenu] Response status:', response.status);
            console.log('[MessageContextMenu] Response ok:', response.ok);

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }

            const data = await response.json();
            console.log('[MessageContextMenu] Response data:', data);
            
            if (data.ok) {
                console.log('[MessageContextMenu] Delete successful');
                console.log('[MessageContextMenu] NOTE: DOM will be updated via WebSocket');
                
                // НЕ удаляем из DOM здесь - это сделает WebSocket handler
                // Так все пользователи увидят удаление в реальном времени
                
                this.showToast('Сообщение удалено');
                console.log('[MessageContextMenu] Toast shown');
            } else {
                throw new Error(data.error || 'Failed to delete message');
            }
        } catch (error) {
            console.error('[MessageContextMenu] Failed to delete message:', error);
            this.showToast('Не удалось удалить сообщение');
        }
    }

    /**
     * Переслать сообщение
     */
    handleForward(messageId) {
        console.log('[ContextMenu] Forward message:', messageId);
        
        // Отправляем событие для активации режима пересылки одного сообщения
        window.dispatchEvent(new CustomEvent('message-forward-single', {
            detail: { messageId }
        }));
        
        this.showToast('Выберите чат для пересылки');
    }

    /**
     * Копировать текст сообщения
     */
    async handleCopy(messageElement) {
        console.log('[ContextMenu] Copy message text');
        
        const bubble = messageElement.querySelector('.bubble');
        if (!bubble) {
            console.warn('[ContextMenu] Bubble not found');
            return;
        }

        // Получаем только текстовое содержимое
        let text = '';
        bubble.childNodes.forEach(node => {
            if (node.nodeType === Node.TEXT_NODE) {
                text += node.textContent;
            } else if (node.nodeName === 'BR') {
                text += '\n';
            } else if (node.classList && !node.classList.contains('message-attachments') && !node.classList.contains('poll-widget')) {
                text += node.textContent;
            }
        });

        text = text.trim();

        try {
            await navigator.clipboard.writeText(text);
            this.showToast('Текст скопирован');
        } catch (err) {
            console.error('[ContextMenu] Failed to copy text:', err);
            this.showToast('Не удалось скопировать');
        }
    }

    /**
     * Выбрать сообщение
     */
    handleSelect(messageElement, messageId) {
        console.log('[ContextMenu] Select message:', messageId);
        
        // Отправляем событие для активации режима выделения
        window.dispatchEvent(new CustomEvent('message-context-menu', {
            detail: {
                action: 'select',
                messageId: messageId,
                messageElement: messageElement
            }
        }));
    }

    /**
     * Получить CSRF токен
     */
    getCsrfToken() {
        const cookie = document.cookie
            .split('; ')
            .find(row => row.startsWith('csrftoken='));
        return cookie ? cookie.split('=')[1] : '';
    }

    /**
     * Экранировать HTML
     */
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    /**
     * Показать временное уведомление
     */
    showToast(message) {
        console.log('[MessageContextMenu] showToast:', message);
        
        const toast = document.createElement('div');
        toast.className = 'context-menu-toast';
        toast.textContent = message;
        
        console.log('[MessageContextMenu] Toast created, appending to body');
        document.body.appendChild(toast);

        requestAnimationFrame(() => {
            console.log('[MessageContextMenu] Adding show class to toast');
            toast.classList.add('show');
        });

        setTimeout(() => {
            console.log('[MessageContextMenu] Removing show class from toast');
            toast.classList.remove('show');
            setTimeout(() => {
                console.log('[MessageContextMenu] Removing toast from DOM');
                toast.remove();
            }, 300);
        }, 2000);
    }

    /**
     * Убрать подсветку сообщения
     */
    removeHighlight() {
        if (this.highlightedMessage) {
            console.log('[MessageContextMenu] Removing highlight from message:', this.highlightedMessage.dataset.messageId);
            this.highlightedMessage.classList.remove('message-highlighted');
            this.highlightedMessage = null;
            console.log('[MessageContextMenu] Highlight removed');
        } else {
            console.log('[MessageContextMenu] No highlighted message to remove');
        }
    }

    /**
     * Закрыть меню
     */
    closeMenu() {
        if (!this.activeMenu) {
            console.log('[MessageContextMenu] closeMenu: no active menu');
            return;
        }

        console.log('[MessageContextMenu] Closing menu');
        
        // Сохраняем ссылку на закрываемое меню
        const menuToClose = this.activeMenu;
        
        // Сразу обнуляем activeMenu (важно для быстрых кликов!)
        this.activeMenu = null;

        // Анимация закрытия
        console.log('[MessageContextMenu] Removing show class for fade out');
        menuToClose.classList.remove('show');
        
        setTimeout(() => {
            console.log('[MessageContextMenu] Removing menu from DOM');
            menuToClose.remove();
        }, 200);
    }
}

export default MessageContextMenu;
