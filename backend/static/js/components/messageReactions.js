// backend/static/js/components/messageReactions.js
/**
 * Компонент для работы с реакциями на сообщения
 */

export class MessageReactions {
    constructor(config = {}) {
        this.apiBaseUrl = config.apiBaseUrl || '/api/v1/communications/messages';
        this.emojis = config.emojis || ['👍', '❤️', '😂', '😮', '😢', '🙏', '👏', '🔥'];
        this.getCsrfToken = config.getCsrfToken || this.defaultGetCsrfToken;
    }

    defaultGetCsrfToken() {
        const cookie = document.cookie
            .split('; ')
            .find(row => row.startsWith('csrftoken='));
        return cookie ? cookie.split('=')[1] : '';
    }

    /**
     * Добавить реакцию на сообщение
     */
    async addReaction(messageId, emoji) {
        try {
            const response = await fetch(`${this.apiBaseUrl}/${messageId}/react/`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.getCsrfToken()
                },
                body: JSON.stringify({ emoji })
            });

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }

            const data = await response.json();
            if (!data.ok) {
                throw new Error(data.error || 'Failed to add reaction');
            }

            return data;
        } catch (error) {
            console.error('Error adding reaction:', error);
            throw error;
        }
    }

    /**
     * Удалить свою реакцию с сообщения
     */
    async removeReaction(messageId) {
        try {
            const response = await fetch(`${this.apiBaseUrl}/${messageId}/unreact/`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.getCsrfToken()
                }
            });

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }

            const data = await response.json();
            if (!data.ok) {
                throw new Error(data.error || 'Failed to remove reaction');
            }

            return data;
        } catch (error) {
            console.error('Error removing reaction:', error);
            throw error;
        }
    }

    /**
     * Получить все реакции для сообщения
     */
    async getReactions(messageId) {
        try {
            const response = await fetch(`${this.apiBaseUrl}/${messageId}/reactions/`);

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }

            const data = await response.json();
            if (!data.ok) {
                throw new Error(data.error || 'Failed to get reactions');
            }

            return data.reactions;
        } catch (error) {
            console.error('Error getting reactions:', error);
            throw error;
        }
    }

    /**
     * Создать HTML для отображения реакций
     * Кнопка добавления реакции убрана - реакции добавляются через контекстное меню
     */
    renderReactions(reactionsSummary, currentUserId) {
        const hasReactions = reactionsSummary && Object.keys(reactionsSummary).length > 0;
        
        // Убедимся, что currentUserId это число
        const userId = parseInt(currentUserId);
        
        let reactionsHtml = '';
        
        if (hasReactions) {
            reactionsHtml = Object.entries(reactionsSummary)
                .map(([emoji, data]) => {
                    const isUserReacted = data.users.includes(userId);
                    const activeClass = isUserReacted ? 'active' : '';
                    const title = data.user_names.join(', ');

                    return `
                        <button 
                            class="reaction-button ${activeClass}" 
                            data-emoji="${emoji}"
                            title="${title}"
                        >
                            <span class="emoji">${emoji}</span>
                            <span class="count">${data.count}</span>
                        </button>
                    `;
                })
                .join('');
        }

        return `
            <div class="message-reactions">
                ${reactionsHtml}
            </div>
        `;
    }

    /**
     * Инициализировать обработчики для сообщения
     */
    /**
     * Инициализация обработчиков реакций для сообщения
     * Кнопка "Добавить реакцию" (➕) убрана - реакции добавляются через контекстное меню
     */
    initMessageReactions(messageElement, messageId, currentUserId) {
        const reactionsContainer = messageElement.querySelector('.message-reactions');
        if (!reactionsContainer) return;

        let longPressTimer = null;
        let longPressTriggered = false;

        // Обработчик начала нажатия (mousedown/touchstart)
        const handlePressStart = (e, reactionBtn) => {
            // Останавливаем всплытие чтобы не срабатывало контекстное меню сообщения
            e.stopPropagation();
            // НЕ вызываем e.preventDefault() чтобы клики работали на мобилках
            
            longPressTriggered = false;
            const emoji = reactionBtn.dataset.emoji;
            const title = reactionBtn.getAttribute('title');
            
            longPressTimer = setTimeout(() => {
                longPressTriggered = true;
                this.showReactionUsers(reactionBtn, emoji, title);
            }, 500); // 500ms для долгого нажатия
        };

        // Обработчик окончания нажатия
        const handlePressEnd = (e) => {
            if (e) {
                e.stopPropagation();
            }
            if (longPressTimer) {
                clearTimeout(longPressTimer);
                longPressTimer = null;
            }
        };

        // Обработчик клика на существующую реакцию (добавить/удалить)
        reactionsContainer.addEventListener('click', async (e) => {
            const reactionBtn = e.target.closest('.reaction-button');
            if (reactionBtn) {
                e.preventDefault();
                e.stopPropagation(); // Останавливаем всплытие
                
                // Если было долгое нажатие - не выполняем клик
                if (longPressTriggered) {
                    longPressTriggered = false;
                    return;
                }
                
                const emoji = reactionBtn.dataset.emoji;
                const isActive = reactionBtn.classList.contains('active');

                try {
                    if (isActive) {
                        // Удалить свою реакцию
                        await this.removeReaction(messageId);
                    } else {
                        // Добавить/изменить реакцию
                        await this.addReaction(messageId, emoji);
                    }
                } catch (error) {
                    console.error('Reaction toggle error:', error);
                }
            }
        });

        // Обработчик правой кнопки мыши (контекстное меню)
        reactionsContainer.addEventListener('contextmenu', (e) => {
            console.log('[MessageReactions] contextmenu event on reactions container');
            const reactionBtn = e.target.closest('.reaction-button');
            if (reactionBtn) {
                console.log('[MessageReactions] contextmenu on reaction button, showing users');
                e.preventDefault();
                e.stopPropagation();
                e.stopImmediatePropagation(); // Останавливаем все обработчики
                
                const emoji = reactionBtn.dataset.emoji;
                const title = reactionBtn.getAttribute('title');
                this.showReactionUsers(reactionBtn, emoji, title);
            }
        }, true); // Используем capturing phase

        // Обработчики долгого нажатия для мыши
        reactionsContainer.addEventListener('mousedown', (e) => {
            const reactionBtn = e.target.closest('.reaction-button');
            if (reactionBtn && e.button === 0) { // Только левая кнопка
                handlePressStart(e, reactionBtn);
            }
        });

        reactionsContainer.addEventListener('mouseup', (e) => {
            handlePressEnd(e);
        });
        
        reactionsContainer.addEventListener('mouseleave', (e) => {
            handlePressEnd(e);
        });

        // Обработчики долгого нажатия для тачскрина
        reactionsContainer.addEventListener('touchstart', (e) => {
            console.log('[MessageReactions] touchstart event on reactions container');
            const reactionBtn = e.target.closest('.reaction-button');
            if (reactionBtn) {
                console.log('[MessageReactions] touchstart on reaction button');
                handlePressStart(e, reactionBtn);
            }
        }, { passive: true, capture: true }); // passive: true чтобы не блокировать скролл

        reactionsContainer.addEventListener('touchend', (e) => {
            const reactionBtn = e.target.closest('.reaction-button');
            
            // Если было долгое нажатие - preventDefault чтобы не было клика
            if (longPressTriggered && reactionBtn) {
                e.preventDefault();
                e.stopPropagation();
                longPressTriggered = false;
            }
            
            handlePressEnd(e);
        });
        
        reactionsContainer.addEventListener('touchcancel', (e) => {
            handlePressEnd(e);
        });
    }

    /**
     * Показать список пользователей, поставивших реакцию
     */
    showReactionUsers(reactionBtn, emoji, userNames) {
        console.log('[MessageReactions] showReactionUsers called', { emoji, userNames });
        
        // Удаляем предыдущий попап если есть
        this.closeReactionUsersPopup();

        // Создаем попап
        const popup = document.createElement('div');
        popup.className = 'reaction-users-popup';
        
        const usersList = userNames.split(', ');
        console.log('[MessageReactions] Users list:', usersList);
        const usersHtml = usersList.map(name => `<div class="user-name">${name}</div>`).join('');
        
        popup.innerHTML = `
            <div class="reaction-users-header">
                <span class="reaction-emoji">${emoji}</span>
                <span class="reaction-count">${usersList.length}</span>
            </div>
            <div class="reaction-users-list">
                ${usersHtml}
            </div>
        `;
        
        document.body.appendChild(popup);
        
        // Позиционируем попап
        const rect = reactionBtn.getBoundingClientRect();
        const popupRect = popup.getBoundingClientRect();
        
        let left = rect.left + (rect.width / 2) - (popupRect.width / 2);
        let top = rect.top - popupRect.height - 8;
        
        // Корректируем если выходит за пределы экрана
        if (left < 8) left = 8;
        if (left + popupRect.width > window.innerWidth - 8) {
            left = window.innerWidth - popupRect.width - 8;
        }
        if (top < 8) {
            top = rect.bottom + 8; // Показываем снизу
        }
        
        popup.style.left = `${left}px`;
        popup.style.top = `${top}px`;
        
        // Сохраняем ссылку на активный попап
        this.activePopup = popup;
        
        // Анимация появления
        requestAnimationFrame(() => {
            popup.classList.add('show');
        });
        
        // Закрываем при клике вне попапа
        const handleClickOutside = (e) => {
            if (this.activePopup && !this.activePopup.contains(e.target) && !e.target.closest('.reaction-button')) {
                this.closeReactionUsersPopup();
            }
        };
        
        // Закрываем при нажатии Escape
        const handleEscape = (e) => {
            if (e.key === 'Escape' && this.activePopup) {
                this.closeReactionUsersPopup();
            }
        };
        
        // Закрываем при скролле
        const handleScroll = () => {
            if (this.activePopup) {
                this.closeReactionUsersPopup();
            }
        };
        
        // Сохраняем обработчики для возможности удаления
        this.popupHandlers = {
            click: handleClickOutside,
            escape: handleEscape,
            scroll: handleScroll
        };
        
        // Добавляем обработчики с небольшой задержкой чтобы не закрыть сразу
        setTimeout(() => {
            document.addEventListener('click', handleClickOutside);
            document.addEventListener('keydown', handleEscape);
            document.addEventListener('scroll', handleScroll, true);
        }, 100);
    }

    /**
     * Закрыть попап списка пользователей
     */
    closeReactionUsersPopup() {
        if (!this.activePopup) {
            return;
        }

        console.log('[MessageReactions] Closing reaction users popup');
        
        const popupToClose = this.activePopup;
        this.activePopup = null;

        // Удаляем обработчики событий
        if (this.popupHandlers) {
            document.removeEventListener('click', this.popupHandlers.click);
            document.removeEventListener('keydown', this.popupHandlers.escape);
            document.removeEventListener('scroll', this.popupHandlers.scroll, true);
            this.popupHandlers = null;
        }

        // Анимация закрытия
        popupToClose.classList.remove('show');
        
        setTimeout(() => {
            popupToClose.remove();
        }, 200);
    }

    /**
     * Обновить отображение реакций для сообщения
     * Работает как с .message-reactions-wrapper так и с .message-reactions напрямую
     */
    updateMessageReactions(messageElement, reactionsSummary, currentUserId) {
        // Обновляем data-reactions атрибут
        messageElement.setAttribute('data-reactions', JSON.stringify(reactionsSummary || {}));
        
        let reactionsContainer = messageElement.querySelector('.message-reactions');
        
        // Если нет реакций - удаляем контейнер
        if (!reactionsSummary || Object.keys(reactionsSummary).length === 0) {
            if (reactionsContainer) {
                reactionsContainer.remove();
            }
            return;
        }
        
        // Рендерим HTML реакций
        const reactionsHtml = this.renderReactions(reactionsSummary, currentUserId);
        
        if (reactionsContainer) {
            // Обновляем существующий контейнер
            reactionsContainer.innerHTML = reactionsHtml;
        } else {
            // Создаем новый контейнер
            const bubble = messageElement.querySelector('.bubble');
            if (bubble) {
                reactionsContainer = document.createElement('div');
                reactionsContainer.className = 'message-reactions mt-2';
                reactionsContainer.innerHTML = reactionsHtml;
                
                // Вставляем перед временем сообщения
                const timeEl = bubble.querySelector('.message-time');
                if (timeEl) {
                    timeEl.parentNode.insertBefore(reactionsContainer, timeEl);
                } else {
                    bubble.appendChild(reactionsContainer);
                }
            }
        }
    }

    /**
     * Обработать WebSocket событие добавления реакции
     */
    handleReactionAdded(data, currentUserId) {
        console.log('[Reactions] === handleReactionAdded START ===');
        console.log('[Reactions] Event data:', JSON.stringify(data));
        console.log('[Reactions] Message ID to find:', data.message_id);
        console.log('[Reactions] Current user ID:', currentUserId);
        
        const messageElements = document.querySelectorAll(`[data-message-id="${data.message_id}"]`);
        console.log('[Reactions] Matched message elements count:', messageElements.length);
        
        if (messageElements.length) {
            messageElements.forEach((messageElement, idx) => {
                console.log(`[Reactions] ✓ Updating element #${idx + 1}:`, messageElement);
                console.log('[Reactions] Element HTML preview:', messageElement.outerHTML.substring(0, 200));
                this.updateMessageReactions(
                    messageElement,
                    data.reactions_summary,
                    currentUserId
                );
            });
        } else {
            console.error('[Reactions] ✗ Message element NOT FOUND for ID:', data.message_id);
            console.log('[Reactions] All message elements:', document.querySelectorAll('[data-message-id]'));
        }
        console.log('[Reactions] === handleReactionAdded END ===');
    }

    /**
     * Обработать WebSocket событие удаления реакции
     */
    handleReactionRemoved(data, currentUserId) {
        console.log('[Reactions] === handleReactionRemoved START ===');
        console.log('[Reactions] Event data:', JSON.stringify(data));
        console.log('[Reactions] Message ID to find:', data.message_id);
        console.log('[Reactions] Current user ID:', currentUserId);
        
        const messageElements = document.querySelectorAll(`[data-message-id="${data.message_id}"]`);
        console.log('[Reactions] Matched message elements count:', messageElements.length);
        
        if (messageElements.length) {
            messageElements.forEach((messageElement, idx) => {
                console.log(`[Reactions] ✓ Updating element #${idx + 1}:`, messageElement);
                console.log('[Reactions] Element HTML preview:', messageElement.outerHTML.substring(0, 200));
                this.updateMessageReactions(
                    messageElement,
                    data.reactions_summary,
                    currentUserId
                );
            });
        } else {
            console.error('[Reactions] ✗ Message element NOT FOUND for ID:', data.message_id);
            console.log('[Reactions] All message elements:', document.querySelectorAll('[data-message-id]'));
        }
        console.log('[Reactions] === handleReactionRemoved END ===');
    }
}

// Экспорт для использования в других модулях
export default MessageReactions;
