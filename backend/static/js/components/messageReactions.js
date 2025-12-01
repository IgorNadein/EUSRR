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

        // Обработчик клика на существующую реакцию (добавить/удалить)
        reactionsContainer.addEventListener('click', async (e) => {
            const reactionBtn = e.target.closest('.reaction-button');
            if (reactionBtn) {
                e.preventDefault();
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
    }

    /**
     * Обновить отображение реакций для сообщения
     */
    updateMessageReactions(messageElement, reactionsSummary, currentUserId) {
        console.log('[Reactions] === updateMessageReactions START ===');
        console.log('[Reactions] Message ID:', messageElement.dataset.messageId);
        console.log('[Reactions] Reactions summary:', JSON.stringify(reactionsSummary));
        console.log('[Reactions] Current user ID:', currentUserId);
        
        const wrapper = messageElement.querySelector('.message-reactions-wrapper');
        
        if (!wrapper) {
            console.error('[Reactions] Message reactions wrapper NOT FOUND!');
            return;
        }

        console.log('[Reactions] Found wrapper:', wrapper);

        // Обновляем data-reactions атрибут для синхронизации состояния
        const dataReactionsValue = JSON.stringify(reactionsSummary || {});
        messageElement.setAttribute('data-reactions', dataReactionsValue);
        console.log('[Reactions] Updated data-reactions attribute:', dataReactionsValue);

        // Обновить содержимое wrapper
        const messageId = messageElement.dataset.messageId;
        const reactionsHtml = this.renderReactions(reactionsSummary, currentUserId);
        console.log('[Reactions] Rendered HTML length:', reactionsHtml.length);
        console.log('[Reactions] Rendered HTML preview:', reactionsHtml.substring(0, 200));
        
        wrapper.innerHTML = reactionsHtml;
        
        console.log('[Reactions] Wrapper updated. Children count:', wrapper.children.length);
        console.log('[Reactions] Wrapper first child:', wrapper.firstElementChild);

        // Переинициализировать обработчики
        this.initMessageReactions(messageElement, messageId, currentUserId);
        console.log('[Reactions] Handlers reinitialized');
        console.log('[Reactions] === updateMessageReactions END ===');
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
