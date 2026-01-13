/**
 * @fileoverview MessageRenderer V2 - рендеринг из Store
 * @module renderers/messageRendererV2
 * 
 * НОВАЯ АРХИТЕКТУРА:
 * - Рендерит только из MessageStore
 * - День-разделители вычисляются Store
 * - Incremental updates (патчинг DOM)
 * - Нет дублирования логики
 */

/**
 * Экранирует HTML для безопасного вывода
 * @param {string} text - Текст для экранирования
 * @returns {string}
 */
function escapeHtml(text) {
    if (!text) return '';
    const map = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#039;'
    };
    return String(text).replace(/[&<>"']/g, m => map[m]);
}

/**
 * MessageRenderer V2 - рендерит сообщения из Store
 */
export class MessageRendererV2 {
    /**
     * @param {Object} options - Опции конфигурации
     * @param {MessageStore} options.store - Экземпляр MessageStore
     * @param {string} options.containerId - ID контейнера для сообщений
     * @param {number} options.currentUserId - ID текущего пользователя
     * @param {string} [options.profileUrl] - URL шаблон профиля
     * @param {string} [options.detailUrlTemplate] - URL шаблон детальной информации
     */
    constructor(options) {
        if (!options.store) {
            throw new Error('[MessageRendererV2] MessageStore is required');
        }

        this.store = options.store;
        this.containerId = options.containerId || 'chatScroll';
        this.currentUserId = options.currentUserId;
        this.profileUrl = options.profileUrl || '/employees/profile/';
        this.detailUrlTemplate = options.detailUrlTemplate || '/employees/detail/0/';

        /** @type {Set<number|string>} ID сообщений которые уже в DOM */
        this.renderedMessages = new Set();

        console.log('[MessageRendererV2] Initialized');
    }

    // ==================== Основные методы рендеринга ====================

    /**
     * Рендерит ВСЕ сообщения чата (full render)
     * @param {number} chatId - ID чата
     * @param {Object} options - Опции
     * @param {boolean} [options.clear=true] - Очистить контейнер перед рендерингом
     * @returns {Promise<void>}
     */
    async render(chatId, options = {}) {
        const container = document.getElementById(this.containerId);
        if (!container) {
            console.error('[MessageRendererV2] Container not found:', this.containerId);
            return;
        }

        const { clear = true } = options;

        // Получаем сообщения с dividers из Store
        const items = this.store.getMessagesWithDividers(chatId);

        if (items.length === 0) {
            if (clear) {
                container.innerHTML = '';
                this.renderedMessages.clear();
            }
            return;
        }

        // Очищаем ДО создания fragment
        if (clear) {
            container.innerHTML = '';
            this.renderedMessages.clear();
        }

        // Используем DocumentFragment для батчинга
        const fragment = document.createDocumentFragment();

        items.forEach(item => {
            if (item.type === 'day-divider') {
                fragment.appendChild(this._createDayDivider(item.text));
            } else if (item.type === 'message') {
                if (!this.renderedMessages.has(item.message.id)) {
                    const messageEl = this._createMessageElement(item.message);
                    fragment.appendChild(messageEl);
                    this.renderedMessages.add(item.message.id);
                }
            }
        });

        // ОДНА вставка в DOM
        container.appendChild(fragment);

        console.log('[MessageRendererV2] Rendered', items.length, 'items');
    }

    /**
     * Добавляет старые сообщения в НАЧАЛО (для истории)
     * @param {Array<Object>} messages - Массив сообщений (от старых к новым)
     * @param {number} chatId - ID чата
     * @returns {DocumentFragment} Fragment с элементами для prepend
     */
    prependMessages(messages, chatId) {
        console.log('[MessageRendererV2] ======================================');
        console.log('[MessageRendererV2] prependMessages called:', {
            messagesCount: messages?.length || 0,
            chatId,
            messageIds: messages?.map(m => m.id) || []
        });
        
        if (!messages || messages.length === 0) {
            console.log('[MessageRendererV2] ❌ No messages to prepend');
            console.log('[MessageRendererV2] ======================================');
            return document.createDocumentFragment();
        }

        console.log('[MessageRendererV2] Prepending', messages.length, 'messages');

        const fragment = document.createDocumentFragment();
        const items = [];

        // Группируем сообщения по дням (от старых к новым)
        let lastDay = null;
        messages.forEach(msg => {
            const msgDate = new Date(msg.created_ts);
            const msgDay = this._formatDay(msgDate);

            // Добавляем divider если день изменился
            if (msgDay !== lastDay) {
                items.push({ type: 'day-divider', text: msgDay });
                lastDay = msgDay;
            }

            items.push({ type: 'message', message: msg });
        });

        console.log('[MessageRendererV2] Items to render:', {
            totalItems: items.length,
            dividers: items.filter(i => i.type === 'day-divider').length,
            messages: items.filter(i => i.type === 'message').length
        });

        // Создаем элементы
        let skipped = 0;
        let added = 0;
        items.forEach(item => {
            if (item.type === 'day-divider') {
                fragment.appendChild(this._createDayDivider(item.text));
                added++;
            } else if (item.type === 'message') {
                if (!this.renderedMessages.has(item.message.id)) {
                    const messageEl = this._createMessageElement(item.message);
                    fragment.appendChild(messageEl);
                    this.renderedMessages.add(item.message.id);
                    added++;
                } else {
                    skipped++;
                    console.log('[MessageRendererV2] ⚠️ Skipped duplicate:', item.message.id);
                }
            }
        });

        console.log('[MessageRendererV2] Fragment created:', {
            added,
            skipped,
            fragmentChildren: fragment.childElementCount
        });
        console.log('[MessageRendererV2] ======================================');

        return fragment;
    }

    /**
     * Удаляет дубликаты day-divider после prepend
     * @param {HTMLElement} container - Контейнер с сообщениями
     */
    _removeDuplicateDividers(container) {
        const dividers = Array.from(container.querySelectorAll('.day-divider'));
        const seen = new Set();
        
        dividers.forEach(divider => {
            const text = divider.textContent.trim();
            if (seen.has(text)) {
                // Удаляем дубликат
                divider.remove();
                console.log('[MessageRendererV2] Removed duplicate divider:', text);
            } else {
                seen.add(text);
            }
        });
    }

    /**
     * Добавляет одно новое сообщение в конец (incremental)
     * @param {Object} message - Сообщение
     * @param {number} chatId - ID чата
     */
    appendMessage(message, chatId) {
        if (!message || !message.id) {
            console.error('[MessageRendererV2] Invalid message:', message);
            return;
        }

        // Проверяем дубликат
        if (this.renderedMessages.has(message.id)) {
            console.log('[MessageRendererV2] Message already rendered:', message.id);
            return;
        }

        const container = document.getElementById(this.containerId);
        if (!container) {
            console.error('[MessageRendererV2] Container not found:', this.containerId);
            return;
        }

        console.log('[MessageRendererV2] Appending message:', message.id);

        // Проверяем нужен ли day-divider
        // Сравниваем с последним сообщением, а не с последним divider
        const lastMessage = container.querySelector('.msg:last-of-type');
        if (lastMessage) {
            const lastMsgId = lastMessage.dataset.messageId;
            const lastMsgData = this.store.getMessage(lastMsgId);
            if (lastMsgData) {
                const lastMsgDate = new Date(lastMsgData.created_ts);
                const lastMsgDay = this._formatDay(lastMsgDate);
                const msgDate = new Date(message.created_ts);
                const msgDay = this._formatDay(msgDate);
                
                // Добавляем divider только если день изменился
                if (msgDay !== lastMsgDay) {
                    container.appendChild(this._createDayDivider(msgDay));
                }
            }
        } else {
            // Первое сообщение - добавляем divider
            const msgDate = new Date(message.created_ts);
            const msgDay = this._formatDay(msgDate);
            container.appendChild(this._createDayDivider(msgDay));
        }

        // Создаем и добавляем сообщение
        const messageEl = this._createMessageElement(message);
        container.appendChild(messageEl);
        this.renderedMessages.add(message.id);
    }

    /**
     * Обновляет существующее сообщение (патчинг)
     * @param {number|string} messageId - ID сообщения
     * @param {Partial<Message>} updates - Обновления
     */
    updateMessage(messageId, updates) {
        const messageEl = document.querySelector(`[data-message-id="${messageId}"]`);
        if (!messageEl) {
            console.warn('[MessageRendererV2] Message element not found:', messageId);
            return;
        }

        console.log('[MessageRendererV2] Updating message:', messageId, updates);

        // Патчим только измененные части
        if (updates.content !== undefined) {
            const contentEl = messageEl.querySelector('.message-content');
            if (contentEl) {
                contentEl.textContent = updates.content;
            }
        }

        if (updates.is_edited !== undefined && updates.is_edited) {
            messageEl.setAttribute('data-is-edited', 'true');
            if (updates.edited_at) {
                messageEl.setAttribute('data-edited-at', String(updates.edited_at));
            }
            
            // Добавляем индикатор редактирования
            const contentEl = messageEl.querySelector('.message-content');
            if (contentEl && !contentEl.querySelector('.edited-indicator')) {
                const indicator = document.createElement('small');
                indicator.className = 'edited-indicator text-muted ms-1';
                indicator.textContent = '(ред.)';
                contentEl.appendChild(indicator);
            }
        }

        if (updates.reactions_summary !== undefined) {
            this._updateReactions(messageEl, updates.reactions_summary);
        }

        if (updates.status !== undefined) {
            this._updateMessageStatus(messageEl, updates.status);
        }
    }

    /**
     * Удаляет сообщение из DOM
     * @param {number|string} messageId - ID сообщения
     */
    removeMessage(messageId) {
        const messageEl = document.querySelector(`[data-message-id="${messageId}"]`);
        if (!messageEl) {
            console.warn('[MessageRendererV2] Message element not found:', messageId);
            return;
        }

        console.log('[MessageRendererV2] Removing message:', messageId);
        
        messageEl.remove();
        this.renderedMessages.delete(messageId);
    }

    // ==================== Создание элементов ====================

    /**
     * Создает элемент day-divider
     * @private
     */
    _createDayDivider(text) {
        const dividerEl = document.createElement('div');
        dividerEl.className = 'day-divider text-center small text-muted my-3';
        dividerEl.innerHTML = `<span class="px-3 py-1 rounded-pill bg-light">${escapeHtml(text)}</span>`;
        return dividerEl;
    }

    /**
     * Создает элемент сообщения
     * @private
     */
    _createMessageElement(msg) {
        const isOwn = msg.author_id === this.currentUserId;
        const messageEl = document.createElement('div');
        
        // Классы
        const classes = ['d-flex', 'mb-3', 'msg'];
        classes.push(isOwn ? 'justify-content-end' : 'justify-content-start');
        
        if (msg.status === 'sending') {
            classes.push('message-pending');
        } else if (msg.status === 'failed') {
            classes.push('message-failed');
        }
        
        messageEl.className = classes.join(' ');

        // Атрибуты
        messageEl.setAttribute('data-id', String(msg.id));
        messageEl.setAttribute('data-message-id', String(msg.id));
        messageEl.setAttribute('data-ts', String(msg.created_ts));
        messageEl.setAttribute('data-author-id', String(msg.author_id || ''));
        messageEl.setAttribute('data-is-edited', String(msg.is_edited || false));
        
        if (msg.edited_at) {
            messageEl.setAttribute('data-edited-at', String(msg.edited_at));
        }
        
        if (msg.reactions_summary) {
            messageEl.setAttribute('data-reactions', JSON.stringify(msg.reactions_summary));
        }

        // HTML содержимое
        messageEl.innerHTML = this._buildMessageInnerHtml(msg, isOwn);

        return messageEl;
    }

    /**
     * Создает внутренний HTML сообщения
     * @private
     */
    _buildMessageInnerHtml(msg, isOwn) {
        const authorName = escapeHtml(msg.author_name || 'Неизвестный');
        const content = escapeHtml(msg.content || '');
        const time = this._formatTime(msg.created_ts);

        // Определяем URL автора
        let authorUrl = this.profileUrl;
        if (msg.author_id && this.detailUrlTemplate) {
            authorUrl = this.detailUrlTemplate.replace('/0/', `/${msg.author_id}/`);
        }

        // Базовая структура
        let html = `
            <div class="message-bubble ${isOwn ? 'bg-primary text-white' : 'bg-light'} rounded-3 p-2 position-relative">
                ${!isOwn ? `
                    <div class="message-author mb-1">
                        <a href="${authorUrl}" class="text-decoration-none fw-bold ${isOwn ? 'text-white' : 'text-primary'}">
                            ${authorName}
                        </a>
                    </div>
                ` : ''}
                
                <div class="message-content">${content}${msg.is_edited ? '<small class="edited-indicator text-muted ms-1">(ред.)</small>' : ''}</div>
                
                ${msg.attachments && msg.attachments.length > 0 ? `
                    <div class="message-attachments mt-2">
                        ${msg.attachments.map(att => this._renderAttachment(att, isOwn)).join('')}
                    </div>
                ` : ''}
                
                <div class="message-time small ${isOwn ? 'text-white-50' : 'text-muted'} mt-1">
                    ${time}
                    ${msg.status === 'sending' ? '<i class="bi bi-clock ms-1"></i>' : ''}
                    ${msg.status === 'failed' ? '<i class="bi bi-exclamation-circle text-danger ms-1"></i>' : ''}
                </div>
                
                ${msg.reactions_summary && Object.keys(msg.reactions_summary).length > 0 ? `
                    <div class="message-reactions mt-2">
                        ${this._renderReactions(msg.reactions_summary)}
                    </div>
                ` : ''}
            </div>
        `;

        return html;
    }

    /**
     * Рендерит вложения
     * @private
     */
    _renderAttachment(att, isOwn) {
        if (!att) return '';
        
        const fileName = escapeHtml(att.file_name || att.name || 'Файл');
        const fileUrl = att.file_url || att.url || '#';
        const fileSize = att.file_size || att.size || 0;
        const fileType = att.file_type || att.type || '';
        
        // Форматируем размер
        const sizeStr = fileSize > 0 
            ? `${(fileSize / 1024).toFixed(1)} KB` 
            : '';
        
        // Определяем иконку по типу
        let icon = 'bi-file-earmark';
        if (fileType.startsWith('image/')) {
            icon = 'bi-file-image';
        } else if (fileType.startsWith('video/')) {
            icon = 'bi-file-play';
        } else if (fileType.includes('pdf')) {
            icon = 'bi-file-pdf';
        } else if (fileType.includes('word') || fileType.includes('document')) {
            icon = 'bi-file-word';
        }
        
        return `
            <a href="${fileUrl}" 
               target="_blank" 
               class="attachment-link d-inline-flex align-items-center text-decoration-none ${isOwn ? 'text-white' : 'text-dark'} mb-1">
                <i class="bi ${icon} me-2"></i>
                <span class="attachment-name">${fileName}</span>
                ${sizeStr ? `<span class="attachment-size ms-2 small opacity-75">(${sizeStr})</span>` : ''}
            </a>
        `;
    }

    /**
     * Рендерит реакции
     * @private
     */
    _renderReactions(reactions) {
        if (!reactions || typeof reactions !== 'object') return '';
        
        return Object.entries(reactions)
            .map(([emoji, count]) => {
                if (count > 0) {
                    return `<span class="reaction-badge badge bg-secondary me-1">${escapeHtml(emoji)} ${count}</span>`;
                }
                return '';
            })
            .join('');
    }

    /**
     * Обновляет реакции сообщения
     * @private
     */
    _updateReactions(messageEl, reactions) {
        let reactionsContainer = messageEl.querySelector('.message-reactions');
        
        if (!reactions || Object.keys(reactions).length === 0) {
            // Удаляем контейнер если нет реакций
            if (reactionsContainer) {
                reactionsContainer.remove();
            }
            return;
        }

        const reactionsHtml = this._renderReactions(reactions);

        if (!reactionsContainer) {
            // Создаем контейнер
            const bubble = messageEl.querySelector('.message-bubble');
            if (bubble) {
                reactionsContainer = document.createElement('div');
                reactionsContainer.className = 'message-reactions mt-2';
                bubble.appendChild(reactionsContainer);
            }
        }

        if (reactionsContainer) {
            reactionsContainer.innerHTML = reactionsHtml;
        }

        // Обновляем data-атрибут
        messageEl.setAttribute('data-reactions', JSON.stringify(reactions));
    }

    /**
     * Обновляет статус сообщения (sending/sent/failed)
     * @private
     */
    _updateMessageStatus(messageEl, status) {
        // Убираем все статусные классы
        messageEl.classList.remove('message-pending', 'message-failed');

        // Добавляем нужный
        if (status === 'sending') {
            messageEl.classList.add('message-pending');
        } else if (status === 'failed') {
            messageEl.classList.add('message-failed');
        }

        // Обновляем иконку в времени
        const timeEl = messageEl.querySelector('.message-time');
        if (timeEl) {
            // Убираем старые иконки
            const icons = timeEl.querySelectorAll('i');
            icons.forEach(icon => icon.remove());

            // Добавляем новую
            if (status === 'sending') {
                timeEl.innerHTML += ' <i class="bi bi-clock ms-1"></i>';
            } else if (status === 'failed') {
                timeEl.innerHTML += ' <i class="bi bi-exclamation-circle text-danger ms-1"></i>';
            }
        }
    }

    // ==================== Утилиты ====================

    /**
     * Форматирует дату в текст дня
     * @private
     */
    _formatDay(date) {
        const today = new Date();
        const yesterday = new Date(today);
        yesterday.setDate(yesterday.getDate() - 1);

        const isToday = date.toDateString() === today.toDateString();
        const isYesterday = date.toDateString() === yesterday.toDateString();

        if (isToday) return 'Сегодня';
        if (isYesterday) return 'Вчера';

        const options = { day: 'numeric', month: 'long', year: 'numeric' };
        return date.toLocaleDateString('ru-RU', options);
    }

    /**
     * Форматирует время
     * @private
     */
    _formatTime(timestamp) {
        const date = new Date(timestamp);
        const hours = String(date.getHours()).padStart(2, '0');
        const minutes = String(date.getMinutes()).padStart(2, '0');
        return `${hours}:${minutes}`;
    }

    /**
     * Очищает контейнер
     */
    clear() {
        const container = document.getElementById(this.containerId);
        if (container) {
            container.innerHTML = '';
            this.renderedMessages.clear();
            console.log('[MessageRendererV2] Container cleared');
        }
    }

    /**
     * Проверяет отрендерено ли сообщение
     * @param {number|string} messageId - ID сообщения
     * @returns {boolean}
     */
    isRendered(messageId) {
        return this.renderedMessages.has(messageId);
    }

    /**
     * Получает статистику
     * @returns {Object}
     */
    getStats() {
        return {
            renderedCount: this.renderedMessages.size,
            containerId: this.containerId
        };
    }
}

export default MessageRendererV2;
