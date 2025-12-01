/**
 * Message Renderer
 * Рендерит сообщения в DOM из JSON данных
 */

export class MessageRenderer {
    constructor(config = {}) {
        this.containerId = config.containerId || 'chatScroll';
        this.currentUserId = config.currentUserId;
        this.currentUserAvatar = config.currentUserAvatar || '';
        this.profileUrl = config.profileUrl || '/employees/profile/';
        this.detailUrlTemplate = config.detailUrlTemplate || '/employees/detail/0/';
    }

    /**
     * Рендерит массив сообщений (с разделителями дней)
     */
    renderMessages(messages) {
        const container = document.getElementById(this.containerId);
        if (!container) {
            console.error('[MessageRenderer] Container not found:', this.containerId);
            return;
        }

        let lastDay = null;
        messages.forEach(msg => {
            // Добавляем разделитель дня если нужно
            const msgDate = new Date(msg.created_ts);
            const msgDay = this.formatDay(msgDate);
            
            if (msgDay !== lastDay) {
                this.addDayDivider(msgDay, container);
                lastDay = msgDay;
            }
            
            this.renderMessage(msg, container);
        });
    }

    /**
     * Добавляет разделитель дня
     */
    addDayDivider(dayText, container = null) {
        if (!container) {
            container = document.getElementById(this.containerId);
        }
        if (!container) return;

        const dividerHtml = `
            <div class="day-divider text-center small text-muted my-3">
                <span class="px-3 py-1 rounded-pill bg-light">${dayText}</span>
            </div>
        `;
        container.insertAdjacentHTML('beforeend', dividerHtml);
    }

    /**
     * Форматирует дату в текст дня
     */
    formatDay(date) {
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
     * Рендерит одно сообщение
     */
    renderMessage(msg, container = null) {
        if (!container) {
            container = document.getElementById(this.containerId);
        }

        // Проверяем, нет ли уже сообщения с таким ID (предотвращаем дубликаты)
        const existingMessage = container.querySelector(`[data-message-id="${msg.id}"]`);
        if (existingMessage) {
            console.log('[MessageRenderer] Message already exists, skipping:', msg.id);
            return;
        }

        const isOwn = msg.author_id === this.currentUserId;
        const messageHtml = this.buildMessageHtml(msg, isOwn);
        
        // Добавляем в конец контейнера
        container.insertAdjacentHTML('beforeend', messageHtml);
    }

    /**
     * Вставляет сообщение в начало (для истории)
     */
    prependMessage(msg) {
        const container = document.getElementById(this.containerId);
        if (!container) return;

        // Проверяем, нет ли уже сообщения с таким ID (предотвращаем дубликаты)
        const existingMessage = container.querySelector(`[data-message-id="${msg.id}"]`);
        if (existingMessage) {
            console.log('[MessageRenderer] Message already exists (prepend), skipping:', msg.id);
            return;
        }

        const isOwn = msg.author_id === this.currentUserId;
        const messageHtml = this.buildMessageHtml(msg, isOwn);
        
        // Находим первое сообщение (не day-divider, не history-loader)
        const firstMsg = container.querySelector('.msg');
        if (firstMsg) {
            firstMsg.insertAdjacentHTML('beforebegin', messageHtml);
        } else {
            container.insertAdjacentHTML('beforeend', messageHtml);
        }
    }

    /**
     * Строит HTML одного сообщения
     */
    buildMessageHtml(msg, isOwn) {
        const authorUrl = isOwn 
            ? this.profileUrl 
            : this.detailUrlTemplate.replace('/0/', `/${msg.author_id}/`);
        
        const authorName = isOwn 
            ? 'Вы' 
            : (msg.author_name || 'Пользователь');

        const avatarHtml = isOwn ? '' : `
            <a class="me-2 text-decoration-none" href="${authorUrl}">
                <span class="mini-ava border">
                    ${msg.avatar 
                        ? `<img src="${msg.avatar}" alt="" loading="lazy">` 
                        : '<i class="bi-person"></i>'}
                </span>
            </a>`;

        const forwardedHtml = msg.is_forwarded && msg.forwarded_from ? `
            <div class="forwarded-indicator small mb-2 d-flex align-items-center">
                <i class="bi-arrow-90deg-right me-2"></i>
                <div>
                    <div>Переслано от <strong>${msg.forwarded_from.author_name || 'Пользователя'}</strong>
                    ${msg.forwarded_from.chat_name ? ` из «${msg.forwarded_from.chat_name}»` : ''}</div>
                    ${msg.forwarded_from.created_at ? `<div class="small opacity-75">${msg.forwarded_from.created_at}</div>` : ''}
                </div>
            </div>` : '';

        const replyHtml = msg.reply_to ? `
            <div class="reply-reference small mb-2" 
                 style="border-left:3px solid var(--bs-primary);padding-left:8px;opacity:0.8;cursor:pointer;"
                 onclick="document.querySelector('[data-message-id=\\\"${msg.reply_to.id}\\\"]')?.scrollIntoView({behavior:'smooth',block:'center'})">
                <div class="fw-semibold">${msg.reply_to.author_name || 'Пользователь'}</div>
                <div class="text-truncate">${this.escapeHtml(msg.reply_to.content || '[файл]')}</div>
            </div>` : '';

        const attachmentsHtml = msg.attachments?.length ? 
            msg.attachments.map(att => this.buildAttachmentHtml(att)).join('') : '';

        // Голосование (опрос)
        const pollHtml = msg.poll ? this.buildPollHtml(msg.poll) : '';

        // Индикатор редактирования
        const editedIndicator = msg.is_edited ? 
            `<span class="message-edited-indicator text-muted small ms-2" style="font-size:0.75rem;font-style:italic;">(изменено)</span>` : '';

        // Реакции теперь рендерятся через message-reactions-wrapper ВНЕ bubble
        // Старая система buildReactionsHtml() больше не используется

        const timeHtml = this.formatTime(msg.created_ts);
        
        // Аватар справа для своих сообщений
        const rightAvatarHtml = isOwn ? `
            <a class="ms-2 text-decoration-none" href="${this.profileUrl}">
                <span class="mini-ava border">
                    ${this.currentUserAvatar 
                        ? `<img src="${this.currentUserAvatar}" alt="" loading="lazy">` 
                        : '<i class="bi-person"></i>'}
                </span>
            </a>` : '';

        return `
<div class="d-flex mb-3 msg ${isOwn ? 'justify-content-end' : 'justify-content-start'}"
     data-id="${msg.id}"
     data-message-id="${msg.id}"
     data-ts="${msg.created_ts}"
     data-author-id="${msg.author_id}"
     data-is-edited="${msg.is_edited || false}"
     data-edited-at="${msg.edited_at || ''}"
     data-reactions='${JSON.stringify(msg.reactions_summary || {})}'>
    ${avatarHtml}
    <div class="d-flex flex-column" style="max-width:80%;">
        <div class="small text-secondary ${isOwn ? 'text-end' : ''}">
            <a href="${authorUrl}" class="text-decoration-none ${isOwn ? '' : 'fw-semibold'}">${authorName}</a>
            · <time datetime="${new Date(msg.created_ts).toISOString()}">${timeHtml}</time>
            ${editedIndicator}
        </div>
        <div class="mt-1 bubble ${isOwn ? 'bubble-me' : 'bubble-other'}">
            ${forwardedHtml}
            ${replyHtml}
            ${msg.content ? `<div>${this.escapeHtml(msg.content)}</div>` : ''}
            ${attachmentsHtml}
            ${pollHtml}
        </div>
        <div class="message-reactions-wrapper mt-1">
        </div>
    </div>
    ${rightAvatarHtml}
</div>`;
    }

    /**
     * Строит HTML вложения
     */
    buildAttachmentHtml(attachment) {
        const fileName = attachment.file_name || attachment.original_filename || 'файл';
        const isImage = attachment.file_url?.match(/\.(jpg|jpeg|png|gif|webp)$/i);
        
        if (isImage) {
            return `
                <div class="attachment-item mb-2">
                    <a href="${attachment.file_url}" target="_blank">
                        <img src="${attachment.file_url}" 
                             alt="${this.escapeHtml(fileName)}" 
                             class="img-fluid rounded"
                             style="max-width:100%;max-height:300px;" 
                             loading="lazy">
                    </a>
                </div>`;
        }

        return `
            <div class="attachment-item mb-2">
                <a href="${attachment.file_url}" 
                   target="_blank" 
                   class="d-flex align-items-center gap-2 text-decoration-none rounded-3 px-3 py-2"
                   title="${this.escapeHtml(fileName)}">
                    <i class="bi-file-earmark"></i>
                    <span class="text-truncate fw-semibold" style="max-width:200px;">${this.escapeHtml(fileName)}</span>
                </a>
            </div>`;
    }

    /**
     * Строит HTML для голосования (опроса)
     */
    buildPollHtml(poll) {
        if (!poll || !poll.id) return '';
        
        const totalVotes = poll.total_voters || 0;
        const isClosed = poll.is_closed || false;
        
        // Базовая структура - детали будут добавлены через ChatPoll.js
        return `
            <div class="poll-widget mt-2" data-poll-id="${poll.id}">
                <div class="poll-question mb-3">
                    <strong>${this.escapeHtml(poll.question)}</strong>
                </div>
                <div class="poll-options">
                    ${poll.options?.map(option => `
                        <div class="poll-option mb-2" data-option-id="${option.id}">
                            <button type="button" class="btn btn-outline-secondary btn-poll-option w-100 text-start" 
                                    data-option-id="${option.id}">
                                ${this.escapeHtml(option.text)}
                            </button>
                        </div>
                    `).join('') || ''}
                </div>
                <div class="poll-footer mt-3 d-flex justify-content-between align-items-center">
                    <div class="small text-muted">
                        ${totalVotes} проголосовало
                        ${poll.is_anonymous ? ' • Анонимное' : ''}
                        ${poll.is_multiple_choice ? ' • Множественный выбор' : ''}
                        ${isClosed ? ' • Закрыто' : ''}
                    </div>
                </div>
            </div>`;
    }

    /**
     * Форматирует дату/время
     */
    formatTime(timestamp) {
        const date = new Date(timestamp);
        const hours = String(date.getHours()).padStart(2, '0');
        const minutes = String(date.getMinutes()).padStart(2, '0');
        return `${hours}:${minutes}`;
    }

    formatDate(timestamp) {
        const date = new Date(timestamp);
        const day = String(date.getDate()).padStart(2, '0');
        const month = String(date.getMonth() + 1).padStart(2, '0');
        const year = date.getFullYear();
        const hours = String(date.getHours()).padStart(2, '0');
        const minutes = String(date.getMinutes()).padStart(2, '0');
        return `${day}.${month}.${year} ${hours}:${minutes}`;
    }

    /**
     * Экранирует HTML
     */
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

/**
 * Фабричная функция для совместимости
 */
export function createMessageRenderer(config) {
    return new MessageRenderer(config);
}
