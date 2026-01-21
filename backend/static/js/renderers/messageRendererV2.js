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

import { DateDividerManager } from '../utils/dateDividers.js';
import { DateGroupManager } from '../managers/dateGroupManager.js';
import MessageReactions from '../components/messageReactions.js';

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
     * @param {DateGroupManager} [options.dateGroupManager] - Менеджер date groups
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
        this.dateGroupManager = options.dateGroupManager || null;
        this.profileUrl = options.profileUrl || '/employees/profile/';
        this.detailUrlTemplate = options.detailUrlTemplate || '/employees/detail/0/';

        /** @type {Set<number|string>} ID сообщений которые уже в DOM */
        this.renderedMessages = new Set();
        
        /** @type {MessageReactions} Централизованный обработчик реакций */
        this.reactions = new MessageReactions();

        console.log('[MessageRendererV2] Initialized', {
            hasDateGroupManager: !!this.dateGroupManager
        });
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

        // Получаем сообщения из Store (без dividers, groupAndRender сам добавит)
        const messages = this.store.getMessagesForChat(chatId);

        if (messages.length === 0) {
            if (clear) {
                container.innerHTML = '';
                this.renderedMessages.clear();
            }
            return;
        }

        // Очищаем ДО рендеринга
        if (clear) {
            container.innerHTML = '';
            this.renderedMessages.clear();
            // Очищаем DateGroupManager если есть
            if (this.dateGroupManager) {
                this.dateGroupManager.clear();
            }
        }

        // Если есть DateGroupManager - используем группировку
        if (this.dateGroupManager) {
            console.log('[MessageRendererV2] Using DateGroupManager for full render');
            
            // Используем groupAndRender для создания date groups
            const groups = this.dateGroupManager.groupAndRender(
                messages,
                (msg) => {
                    this.renderedMessages.add(msg.id);
                    return this._createMessageElement(msg);
                },
                'append'
            );
            
            console.log('[MessageRendererV2] Rendered', messages.length, 'messages in', groups.length, 'date groups');
            return;
        }

        // Fallback: старая логика без DateGroupManager
        console.log('[MessageRendererV2] Using legacy rendering (no DateGroupManager)');
        
        // Получаем сообщения с dividers из Store
        const items = this.store.getMessagesWithDividers(chatId);

        // Используем DocumentFragment для батчинга
        const fragment = document.createDocumentFragment();

        items.forEach(item => {
            if (item.type === 'divider') {
                fragment.appendChild(DateDividerManager.createDivider(item.text));
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

        console.log('[MessageRendererV2] Rendered', items.length, 'items (legacy mode)');
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
        
        // Если есть DateGroupManager - используем группировку
        if (this.dateGroupManager) {
            console.log('[MessageRendererV2] Using DateGroupManager');
            
            // Создаем группы с помощью DateGroupManager
            const groups = this.dateGroupManager.groupAndRender(
                messages,
                (msg) => {
                    if (!this.renderedMessages.has(msg.id)) {
                        this.renderedMessages.add(msg.id);
                        return this._createMessageElement(msg);
                    }
                    return null;
                },
                'prepend' // Важно: указываем что это prepend
            );
            
            // Добавляем все группы в fragment
            groups.forEach(group => fragment.appendChild(group));
            
            console.log('[MessageRendererV2] Created', groups.length, 'date groups');
            console.log('[MessageRendererV2] ======================================');
            return fragment;
        }
        
        // Fallback: старая логика без групп
        console.log('[MessageRendererV2] Using legacy dividers (no DateGroupManager)');
        const items = [];

        // Группируем сообщения по дням (от старых к новым)
        let lastDay = null;
        messages.forEach(msg => {
            const msgDate = new Date(msg.created_ts);
            const msgDay = DateDividerManager.formatDay(msgDate);

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
                fragment.appendChild(DateDividerManager.createDivider(item.text));
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
     * Добавляет новые сообщения в КОНЕЦ (для загрузки при прокрутке вниз после перехода по дате)
     * Как в Telegram: при прокрутке вниз после перехода к старой дате
     * @param {Array<Object>} messages - Массив сообщений (от старых к новым)
     * @param {number} chatId - ID чата
     * @returns {DocumentFragment} Fragment с элементами для append
     */
    appendMessages(messages, chatId) {
        console.log('[MessageRendererV2] ======================================');
        console.log('[MessageRendererV2] appendMessages called:', {
            messagesCount: messages?.length || 0,
            chatId,
            messageIds: messages?.map(m => m.id) || []
        });
        
        if (!messages || messages.length === 0) {
            console.log('[MessageRendererV2] ❌ No messages to append');
            console.log('[MessageRendererV2] ======================================');
            return document.createDocumentFragment();
        }

        console.log('[MessageRendererV2] Appending', messages.length, 'messages');

        const fragment = document.createDocumentFragment();
        
        // Если есть DateGroupManager - используем группировку
        if (this.dateGroupManager) {
            console.log('[MessageRendererV2] Using DateGroupManager for append');
            
            // Создаем группы с помощью DateGroupManager
            const groups = this.dateGroupManager.groupAndRender(
                messages,
                (msg) => {
                    if (!this.renderedMessages.has(msg.id)) {
                        this.renderedMessages.add(msg.id);
                        return this._createMessageElement(msg);
                    }
                    return null;
                },
                'append' // Указываем что это append
            );
            
            // Добавляем все группы в fragment
            groups.forEach(group => fragment.appendChild(group));
            
            console.log('[MessageRendererV2] Created', groups.length, 'date groups for append');
            console.log('[MessageRendererV2] ======================================');
            return fragment;
        }
        
        // Fallback: старая логика без групп
        console.log('[MessageRendererV2] Using legacy dividers for append (no DateGroupManager)');
        const items = [];

        // Получаем последний день из контейнера для корректных divider'ов
        const container = document.getElementById(this.containerId);
        const lastDivider = container?.querySelector('.day-divider:last-of-type');
        let lastDay = lastDivider ? lastDivider.textContent.trim() : null;

        // Группируем сообщения по дням (от старых к новым)
        messages.forEach(msg => {
            const msgDate = new Date(msg.created_ts);
            const msgDay = DateDividerManager.formatDay(msgDate);

            // Добавляем divider если день изменился
            if (msgDay !== lastDay) {
                items.push({ type: 'day-divider', text: msgDay });
                lastDay = msgDay;
            }

            items.push({ type: 'message', message: msg });
        });

        console.log('[MessageRendererV2] Items to append:', {
            totalItems: items.length,
            dividers: items.filter(i => i.type === 'day-divider').length,
            messages: items.filter(i => i.type === 'message').length
        });

        // Создаем элементы
        let skipped = 0;
        let added = 0;
        items.forEach(item => {
            if (item.type === 'day-divider') {
                fragment.appendChild(DateDividerManager.createDivider(item.text));
                added++;
            } else if (item.type === 'message') {
                if (!this.renderedMessages.has(item.message.id)) {
                    const messageEl = this._createMessageElement(item.message);
                    fragment.appendChild(messageEl);
                    this.renderedMessages.add(item.message.id);
                    added++;
                } else {
                    skipped++;
                    console.log('[MessageRendererV2] ⚠️ Skipped duplicate in append:', item.message.id);
                }
            }
        });

        console.log('[MessageRendererV2] Append fragment created:', {
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

        // Если есть DateGroupManager - используем группировку
        if (this.dateGroupManager) {
            const messageDate = DateDividerManager.getMessageDate(message);
            const dateText = DateDividerManager.formatDay(messageDate);
            
            // Создаем элемент сообщения
            const messageEl = this._createMessageElement(message);
            
            // Добавляем в соответствующую группу
            this.dateGroupManager.addMessageToGroup(
                messageEl,
                dateText,
                messageDate.getTime(),
                'append'
            );
            
            this.renderedMessages.add(message.id);
            console.log('[MessageRendererV2] Message added to date group:', dateText);
            return;
        }

        // Fallback: старая логика без групп
        // Проверяем нужен ли day-divider
        // Сравниваем с последним сообщением, а не с последним divider
        const lastMessage = container.querySelector('.msg:last-of-type');
        if (lastMessage) {
            const lastMsgId = lastMessage.dataset.messageId;
            const lastMsgData = this.store.getMessage(lastMsgId);
            if (lastMsgData) {
                const lastMsgDate = new Date(lastMsgData.created_ts);
                const lastMsgDay = DateDividerManager.formatDay(lastMsgDate);
                const msgDate = new Date(message.created_ts);
                const msgDay = DateDividerManager.formatDay(msgDate);
                
                // Добавляем divider только если день изменился
                if (msgDay !== lastMsgDay) {
                    container.appendChild(DateDividerManager.createDivider(msgDay));
                }
            }
        } else {
            // Первое сообщение - добавляем divider
            const msgDate = new Date(message.created_ts);
            const msgDay = DateDividerManager.formatDay(msgDate);
            container.appendChild(DateDividerManager.createDivider(msgDay));
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
            // Используем централизованный MessageReactions для обновления
            this.reactions.updateMessageReactions(messageEl, updates.reactions_summary, this.currentUserId);
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
    
    /**
     * Рендерит одно сообщение (для редактирования)
     * @param {Object} message - данные сообщения
     * @returns {HTMLElement} - DOM элемент сообщения
     */
    renderSingleMessage(message) {
        return this._createMessageElement(message);
    }

    // ==================== Создание элементов ====================

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

        // HTML содержимое с аватаром для чужих сообщений
        let html = '';
        
        // Аватар для чужих сообщений (слева)
        if (!isOwn) {
            // Проверяем разные варианты поля с аватаром
            const avatarUrl = msg.author_avatar || msg.avatar || msg.author?.avatar || '';
            console.log('[MessageRendererV2] Avatar debug:', {
                author_avatar: msg.author_avatar,
                avatar: msg.avatar,
                author: msg.author,
                avatarUrl,
                message: msg
            });
            
            // Всегда создаем контейнер .mini-ava
            html += '<div class="mini-ava me-2">';
            if (avatarUrl) {
                html += `<img src="${avatarUrl}" alt="${escapeHtml(msg.author_name || '')}"/>`;
            } else {
                html += '<i class="bi bi-person-circle"></i>';
            }
            html += '</div>';
        }
        
        // Bubble с содержимым
        html += this._buildMessageInnerHtml(msg, isOwn);
        
        messageEl.innerHTML = html;
        
        // Добавляем обработчик клика на reply preview для навигации
        if (msg.reply_to) {
            const replyPreview = messageEl.querySelector('.message-reply-preview');
            if (replyPreview) {
                replyPreview.addEventListener('click', (e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    this._scrollToMessage(msg.reply_to.id);
                });
                
                // Поддержка клавиатуры (Enter)
                replyPreview.addEventListener('keydown', (e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                        e.preventDefault();
                        this._scrollToMessage(msg.reply_to.id);
                    }
                });
            }
        }
        
        // Инициализация виджета опроса если есть
        if (msg.poll && window.chatPoll) {
            const pollWidget = messageEl.querySelector('.poll-widget');
            if (pollWidget) {
                const pollId = msg.poll.id;
                // Даём время для вставки в DOM и инициализируем
                setTimeout(() => {
                    window.chatPoll.refreshPoll(pollId, pollWidget);
                }, 0);
            }
        }

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

        // Базовая структура с BEM-модификаторами
        let bubbleModifier = isOwn ? 'bubble--me' : 'bubble--other';
        
        // Системные сообщения (без автора)
        if (!msg.author_id || msg.is_system) {
            bubbleModifier = 'bubble--system';
        }
        
        let html = `<div class="bubble ${bubbleModifier}">`;
        
        // Имя автора для чужих сообщений
        if (!isOwn) {
            html += '<div class="bubble__author">';
            html += `<a href="${authorUrl}">${authorName}</a>`;
            html += '</div>';
        }
        
        // Информация о пересылке
        if (msg.is_forwarded && msg.forwarded_from) {
            html += this._renderForwardInfo(msg.forwarded_from);
        }
        
        // Ответ на сообщение (reply preview) - bubble__reply-preview добавляется внутри _renderReplyPreview
        if (msg.reply_to) {
            html += this._renderReplyPreview(msg.reply_to, isOwn);
        }
        
        // Контент
        html += `<div class="bubble__content">${content}`;
        if (msg.is_edited) {
            html += '<span class="bubble__edited">(ред.)</span>';
        }
        html += '</div>';
        
        // Голосование
        if (msg.poll) {
            html += '<div class="bubble__poll">';
            html += this._renderPoll(msg.poll);
            html += '</div>';
        }
        
        // Вложения
        if (msg.attachments && msg.attachments.length > 0) {
            html += '<div class="bubble__attachments">';
            html += msg.attachments.map(att => this._renderAttachment(att, isOwn)).join('');
            html += '</div>';
        }
        
        // Время
        html += '<div class="bubble__time">';
        html += time;
        if (msg.status === 'sending') html += ' <i class="bi bi-clock"></i>';
        if (msg.status === 'failed') html += ' <i class="bi bi-exclamation-circle text-danger"></i>';
        html += '</div>';
        
        // Реакции (используем централизованный MessageReactions)
        if (msg.reactions_summary && Object.keys(msg.reactions_summary).length > 0) {
            html += '<div class="bubble__reactions">';
            html += this.reactions.renderReactions(msg.reactions_summary, this.currentUserId);
            html += '</div>';
        }
        
        html += '</div>';

        return html;
    }

    /**
     * Рендерит превью ответа на сообщение
     * @private
     * @param {Object} replyTo - Данные исходного сообщения
     * @param {boolean} isOwn - Своё ли это сообщение
     * @returns {string} HTML превью
     */
    _renderReplyPreview(replyTo, isOwn) {
        if (!replyTo) return '';
        
        const authorName = escapeHtml(replyTo.author_name || 'Пользователь');
        const content = escapeHtml(replyTo.content || 'Сообщение');
        const replyId = replyTo.id || '';
        
        // Используем BEM классы вместо inline стилей
        const modifierClass = isOwn ? 'message-reply-preview--own' : 'message-reply-preview--other';
        
        return `
            <div class="message-reply-preview ${modifierClass}" 
                 data-reply-to-id="${replyId}"
                 role="button"
                 tabindex="0"
                 title="Нажмите для перехода к сообщению">
                <div class="message-reply-preview__author small fw-semibold">
                    <i class="bi bi-reply-fill"></i>
                    ${authorName}
                </div>
                <div class="message-reply-preview__content small text-truncate">
                    ${content}
                </div>
            </div>
        `;
    }

    /**     * Рендерит информацию о пересылке
     * @private
     * @param {Object} forwardedFrom - Данные оригинального сообщения
     * @returns {string} HTML плашки пересылки
     */
    _renderForwardInfo(forwardedFrom) {
        if (!forwardedFrom) return '';
        
        const authorName = escapeHtml(forwardedFrom.author_name || 'Пользователь');
        const chatName = forwardedFrom.chat_name ? ` из «${escapeHtml(forwardedFrom.chat_name)}»` : '';
        const createdAt = forwardedFrom.created_at || '';
        
        return `
            <div class="bubble__forward">
                <i class="bi bi-arrow-90deg-right me-1"></i>
                Переслано от <strong>${authorName}</strong>${chatName}
                ${createdAt ? `<div class="small opacity-75">${createdAt}</div>` : ''}
            </div>
        `;
    }

    /**     * Рендерит вложения
     * @private
     */
    _renderAttachment(att, isOwn) {
        if (!att) return '';
        
        const fileName = escapeHtml(att.file_name || att.name || 'Файл');
        const fileUrl = att.file_url || att.url || '#';
        const fileSize = att.file_size || att.size || 0;
        const fileType = att.file_type || att.type || '';
        const thumbnailUrl = att.thumbnail || null;
        const attachmentId = att.id || '';
        const width = att.width || null;
        const height = att.height || null;
        
        // Рендеринг изображений
        if (fileType === 'image' || fileType.startsWith('image/')) {
            const imgSrc = thumbnailUrl || fileUrl;
            
            // 🐛 DEBUG: Проверяем размеры изображения
            console.log(`[IMAGE DEBUG] Attachment #${attachmentId}: ${fileName}`, {
                width, height,
                hasSize: !!(width && height),
                url: imgSrc
            });
            
            // Telegram approach: вычисляем точные размеры в пикселях
            let dimensionStyle = '';
            if (width && height) {
                const maxWidth = 500; // Максимальная ширина как в Telegram
                const scale = Math.min(1, maxWidth / width);
                const w = Math.round(width * scale);
                const h = Math.round(height * scale);
                
                dimensionStyle = `style="width: ${w}px; height: ${h}px;"`;
                console.log(`[IMAGE DEBUG] ✅ Telegram approach: ${w}x${h}px (original: ${width}x${height}, scale: ${scale.toFixed(2)})`);
            } else {
                console.warn(`[IMAGE DEBUG] ⚠️ Размеры отсутствуют! Возможно смещение скролла`);
            }
            
            // Генерируем unique ID для изображения
            const imgId = `img-${attachmentId}-${Date.now()}`;
            
            // Добавляем onload через setTimeout после рендера
            setTimeout(() => {
                const img = document.getElementById(imgId);
                if (img) {
                    img.addEventListener('load', () => {
                        console.log(`[IMAGE DEBUG] 📊 Изображение загружено: #${attachmentId}`, {
                            naturalWidth: img.naturalWidth,
                            naturalHeight: img.naturalHeight,
                            displayWidth: img.clientWidth,
                            displayHeight: img.clientHeight,
                            expectedRatio: width && height ? (width / height).toFixed(2) : 'unknown',
                            actualRatio: img.naturalWidth && img.naturalHeight ? (img.naturalWidth / img.naturalHeight).toFixed(2) : 'unknown'
                        });
                    });
                }
            }, 0);
            
            return `
                <a href="${fileUrl}" target="_blank" class="attachment-item attachment-item--media d-block" data-attachment-id="${attachmentId}">
                    <img id="${imgId}"
                         src="${imgSrc}" 
                         alt="${fileName}" 
                         class="chat-media chat-media--image"
                         ${dimensionStyle}
                         loading="lazy" />
                </a>
            `;
        }
        
        // Рендеринг видео
        if (fileType === 'video' || fileType.startsWith('video/')) {
            return `
                <div class="attachment-item attachment-item--media" data-attachment-id="${attachmentId}">
                    <video src="${fileUrl}" 
                           class="chat-media chat-media--video"
                           controls
                           playsinline
                           preload="metadata">
                        Ваш браузер не поддерживает воспроизведение видео.
                    </video>
                </div>
            `;
        }
        
        // Форматируем размер для файлов
        const sizeStr = fileSize > 0 
            ? `${(fileSize / 1024).toFixed(1)} KB` 
            : '';
        
        // Определяем иконку для файлов
        let icon = 'bi-file-earmark';
        if (fileType.includes('pdf')) {
            icon = 'bi-file-pdf';
        } else if (fileType.includes('word') || fileType.includes('document')) {
            icon = 'bi-file-word';
        } else if (fileType.startsWith('audio/')) {
            icon = 'bi-file-music';
        }
        
        // Рендеринг обычных файлов (документы, аудио и т.д.)
        return `
            <a href="${fileUrl}" 
               target="_blank" 
               class="attachment-link d-inline-flex align-items-center text-decoration-none ${isOwn ? 'text-white' : 'text-dark'} mb-1"
               data-attachment-id="${attachmentId}">
                <i class="bi ${icon} me-2"></i>
                <span class="attachment-name">${fileName}</span>
                ${sizeStr ? `<span class="attachment-size ms-2 small opacity-75">(${sizeStr})</span>` : ''}
            </a>
        `;
    }

    /**
     * Рендерит голосование
     * @private
     */
    _renderPoll(poll) {
        if (!poll) return '';
        
        // Базовая структура poll widget
        let html = `<div class="poll-widget" data-poll-id="${poll.id}">`;
        
        // Вопрос
        html += `<div class="poll-question mb-3"><strong>${escapeHtml(poll.question)}</strong></div>`;
        
        // Контейнер для опций (заполнится через chatPoll.refreshPoll)
        html += '<div class="poll-options"></div>';
        
        // Футер
        html += '<div class="poll-footer mt-3 d-flex justify-content-between align-items-center">';
        html += '<div class="small text-muted">Загрузка...</div>';
        html += '</div>';
        
        html += '</div>';
        
        return html;
    }

    // Методы рендеринга и обновления реакций удалены - используется MessageReactions

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
            
            // Очищаем DateGroupManager если есть
            if (this.dateGroupManager) {
                this.dateGroupManager.clear();
            }
            
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
     * Скроллит к указанному сообщению с подсветкой
     * @private
     * @param {number|string} messageId - ID сообщения
     */
    _scrollToMessage(messageId) {
        const targetEl = document.querySelector(`[data-message-id="${messageId}"]`);
        if (targetEl) {
            // Скроллим к сообщению
            targetEl.scrollIntoView({ behavior: 'smooth', block: 'center' });
            
            // Добавляем анимацию подсветки к .msg (всей линии)
            targetEl.classList.remove('highlight-flash');
            setTimeout(() => {
                targetEl.classList.add('highlight-flash');
                setTimeout(() => targetEl.classList.remove('highlight-flash'), 1500);
            }, 10);
            
            console.log('[MessageRendererV2] Scrolled to message:', messageId);
        } else {
            console.warn('[MessageRendererV2] Message not found in viewport:', messageId);
            // TODO: Загрузить сообщение если оно не в viewport
        }
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
