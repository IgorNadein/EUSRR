// Enhanced Chat Detail with new messenger features
(function() {
    'use strict';

    const chatScroll = document.getElementById('chatScroll');
    if (!chatScroll) return;

    const chatId = chatScroll.dataset.chatId;
    const meId = parseInt(chatScroll.dataset.meId);
    
    let ws = null;
    let typingTimeout = null;
    let reconnectAttempts = 0;
    const MAX_RECONNECT = 5;

    // State
    const state = {
        editingMessageId: null,
        replyToMessageId: null,
        selectedMessages: new Set()
    };

    // ==================== WebSocket ====================
    
    function connectWebSocket() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws/chat/${chatId}/`;
        
        ws = new WebSocket(wsUrl);
        
        ws.onopen = () => {
            console.log('WebSocket connected');
            reconnectAttempts = 0;
        };
        
        ws.onmessage = (e) => {
            const data = JSON.parse(e.data);
            handleWebSocketMessage(data);
        };
        
        ws.onerror = (e) => {
            console.error('WebSocket error:', e);
        };
        
        ws.onclose = () => {
            console.log('WebSocket closed');
            if (reconnectAttempts < MAX_RECONNECT) {
                reconnectAttempts++;
                setTimeout(connectWebSocket, 2000 * reconnectAttempts);
            }
        };
    }

    function handleWebSocketMessage(data) {
        switch(data.type) {
            case 'message_edited':
                updateMessage(data.message);
                break;
            case 'message_deleted':
                markMessageAsDeleted(data.message_id);
                break;
            case 'reaction_added':
            case 'reaction_removed':
                updateReactions(data.message_id, data.reactions);
                break;
            case 'user_typing':
                showTypingIndicator(data.user_name);
                break;
            case 'user_stopped_typing':
                hideTypingIndicator();
                break;
            default:
                // New message
                if (data.id) {
                    appendMessage(data);
                }
        }
    }

    function sendAction(action, payload) {
        if (ws && ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ action, ...payload }));
        }
    }

    // ==================== Message Rendering ====================

    function appendMessage(msg) {
        const isMe = msg.author_id === meId;
        const existingMsg = document.querySelector(`[data-id="${msg.id}"]`);
        if (existingMsg) {
            updateMessage(msg);
            return;
        }

        const msgHtml = renderMessage(msg, isMe);
        chatScroll.insertAdjacentHTML('beforeend', msgHtml);
        scrollToBottom();
    }

    function renderMessage(msg, isMe) {
        const timeStr = new Date(msg.created_ts).toLocaleTimeString('ru', {hour: '2-digit', minute: '2-digit'});
        
        let html = `
        <div class="d-flex mb-3 msg ${isMe ? 'justify-content-end' : 'justify-content-start'}"
             data-id="${msg.id}"
             data-ts="${msg.created_ts}"
             data-author-id="${msg.author_id}">
        `;

        // Avatar (left side for others)
        if (!isMe && msg.avatar) {
            html += `
            <a class="me-2 text-decoration-none" href="${msg.author_url}">
                <span class="mini-ava border">
                    <img src="${msg.avatar}" alt="" loading="lazy">
                </span>
            </a>`;
        }

        html += `<div class="d-flex flex-column" style="max-width:80%;">`;
        
        // Author & time
        html += `<div class="small text-secondary ${isMe ? 'text-end' : ''}">`;
        if (isMe) {
            html += `<a href="/employees/profile/" class="text-decoration-none">Вы</a>`;
        } else {
            html += `<a href="${msg.author_url}" class="text-decoration-none fw-semibold">${msg.author_name}</a>`;
        }
        html += ` · <time>${timeStr}</time>`;
        if (msg.is_edited) {
            html += ` <i class="bi-pencil-fill text-muted" title="Изменено"></i>`;
        }
        html += `</div>`;

        // Reply preview
        if (msg.reply_to) {
            html += `
            <div class="reply-preview mb-1">
                <i class="bi-reply"></i>
                <span class="fw-semibold">${msg.reply_to.author_name}:</span>
                ${escapeHtml(msg.reply_to.content.substring(0, 50))}
            </div>`;
        }

        // Forward info
        if (msg.is_forwarded && msg.forward_info) {
            html += `
            <div class="forward-info mb-1">
                <i class="bi-forward"></i>
                Переслано от ${msg.forward_info.original_author}
                ${msg.forward_info.forward_count > 1 ? `(×${msg.forward_info.forward_count})` : ''}
            </div>`;
        }

        // Message bubble
        const bubbleClass = isMe ? 'bubble-me' : 'bubble-other';
        html += `<div class="mt-1 bubble ${bubbleClass} position-relative">`;
        
        if (msg.is_deleted) {
            html += `<em class="text-muted">Сообщение удалено</em>`;
        } else {
            html += escapeHtml(msg.content).replace(/\n/g, '<br>');
        }

        // Attachments
        if (msg.attachments && msg.attachments.length > 0) {
            html += `<div class="attachments mt-2">`;
            msg.attachments.forEach(att => {
                if (att.file_type === 'image') {
                    html += `
                    <a href="${att.file_url}" target="_blank">
                        <img src="${att.thumbnail || att.file_url}" class="attachment-image" alt="${att.file_name}">
                    </a>`;
                } else {
                    html += `
                    <a href="${att.file_url}" class="attachment-file" download>
                        <i class="bi-file-earmark"></i> ${att.file_name}
                    </a>`;
                }
            });
            html += `</div>`;
        }

        // Pinned indicator
        if (msg.is_pinned) {
            html += `<i class="bi-pin-angle-fill position-absolute top-0 end-0 m-1"></i>`;
        }

        // Message actions
        if (isMe && !msg.is_deleted) {
            html += `
            <div class="message-actions">
                <button class="btn btn-sm btn-ghost" onclick="editMessage(${msg.id})" title="Редактировать">
                    <i class="bi-pencil"></i>
                </button>
                <button class="btn btn-sm btn-ghost" onclick="deleteMessage(${msg.id})" title="Удалить">
                    <i class="bi-trash"></i>
                </button>
            </div>`;
        }

        html += `</div>`; // bubble

        // Reactions
        if (msg.reactions && Object.keys(msg.reactions).length > 0) {
            html += `<div class="reactions mt-1" data-message-id="${msg.id}">`;
            for (const [emoji, userIds] of Object.entries(msg.reactions)) {
                const isMyReaction = userIds.includes(meId);
                html += `
                <button class="reaction-btn ${isMyReaction ? 'active' : ''}" 
                        data-emoji="${emoji}"
                        onclick="toggleReaction(${msg.id}, '${emoji}')">
                    ${emoji} <span class="count">${userIds.length}</span>
                </button>`;
            }
            html += `</div>`;
        }

        // Quick reactions (on hover)
        html += `
        <div class="quick-reactions">
            <button onclick="addReaction(${msg.id}, '👍')">👍</button>
            <button onclick="addReaction(${msg.id}, '❤️')">❤️</button>
            <button onclick="addReaction(${msg.id}, '😊')">😊</button>
            <button onclick="addReaction(${msg.id}, '🔥')">🔥</button>
            <button onclick="setReplyTo(${msg.id})"><i class="bi-reply"></i></button>
            <button onclick="forwardMessage(${msg.id})"><i class="bi-forward"></i></button>
        </div>`;

        html += `</div>`; // flex-column

        // Avatar (right side for me)
        if (isMe) {
            const myAvatar = document.querySelector('.mini-ava img')?.src || '';
            html += `
            <a class="ms-2 text-decoration-none" href="/employees/profile/">
                <span class="mini-ava border">
                    ${myAvatar ? `<img src="${myAvatar}" alt="" loading="lazy">` : '<i class="bi-person"></i>'}
                </span>
            </a>`;
        }

        html += `</div>`; // msg container

        return html;
    }

    function updateMessage(msg) {
        const msgEl = document.querySelector(`[data-id="${msg.id}"]`);
        if (!msgEl) return;

        const isMe = msg.author_id === meId;
        const newHtml = renderMessage(msg, isMe);
        msgEl.outerHTML = newHtml;
    }

    function markMessageAsDeleted(messageId) {
        const msgEl = document.querySelector(`[data-id="${messageId}"]`);
        if (!msgEl) return;

        const bubble = msgEl.querySelector('.bubble');
        if (bubble) {
            bubble.innerHTML = '<em class="text-muted">Сообщение удалено</em>';
        }
    }

    function updateReactions(messageId, reactions) {
        const msgEl = document.querySelector(`[data-id="${messageId}"]`);
        if (!msgEl) return;

        let reactionsContainer = msgEl.querySelector('.reactions');
        
        if (Object.keys(reactions).length === 0) {
            if (reactionsContainer) reactionsContainer.remove();
            return;
        }

        if (!reactionsContainer) {
            const bubble = msgEl.querySelector('.bubble');
            reactionsContainer = document.createElement('div');
            reactionsContainer.className = 'reactions mt-1';
            reactionsContainer.dataset.messageId = messageId;
            bubble.after(reactionsContainer);
        }

        let html = '';
        for (const [emoji, userIds] of Object.entries(reactions)) {
            const isMyReaction = userIds.includes(meId);
            html += `
            <button class="reaction-btn ${isMyReaction ? 'active' : ''}" 
                    data-emoji="${emoji}"
                    onclick="toggleReaction(${messageId}, '${emoji}')">
                ${emoji} <span class="count">${userIds.length}</span>
            </button>`;
        }
        reactionsContainer.innerHTML = html;
    }

    // ==================== Actions ====================

    window.editMessage = function(messageId) {
        const msgEl = document.querySelector(`[data-id="${messageId}"]`);
        const bubble = msgEl.querySelector('.bubble');
        const content = bubble.textContent.trim();

        state.editingMessageId = messageId;
        
        const textarea = document.getElementById('id_content');
        textarea.value = content;
        textarea.focus();

        showEditingIndicator(messageId);
    };

    window.deleteMessage = function(messageId) {
        if (!confirm('Удалить сообщение?')) return;
        
        sendAction('delete_message', { message_id: messageId });
    };

    window.addReaction = function(messageId, emoji) {
        sendAction('add_reaction', { message_id: messageId, emoji });
    };

    window.toggleReaction = function(messageId, emoji) {
        const msgEl = document.querySelector(`[data-id="${messageId}"]`);
        const reactionBtn = msgEl.querySelector(`.reaction-btn[data-emoji="${emoji}"]`);
        
        if (reactionBtn.classList.contains('active')) {
            sendAction('remove_reaction', { message_id: messageId, emoji });
        } else {
            sendAction('add_reaction', { message_id: messageId, emoji });
        }
    };

    window.setReplyTo = function(messageId) {
        const msgEl = document.querySelector(`[data-id="${messageId}"]`);
        const bubble = msgEl.querySelector('.bubble');
        const authorName = msgEl.querySelector('.fw-semibold')?.textContent || 'Вы';
        const content = bubble.textContent.trim();

        state.replyToMessageId = messageId;

        showReplyIndicator(authorName, content);
        document.getElementById('id_content').focus();
    };

    window.forwardMessage = function(messageId) {
        // TODO: Show modal to select target chat
        console.log('Forward message:', messageId);
    };

    // ==================== UI Helpers ====================

    function showEditingIndicator(messageId) {
        const indicator = document.createElement('div');
        indicator.id = 'editing-indicator';
        indicator.className = 'alert alert-info d-flex align-items-center';
        indicator.innerHTML = `
            <i class="bi-pencil me-2"></i>
            Редактирование сообщения
            <button type="button" class="btn-close ms-auto" onclick="cancelEdit()"></button>
        `;
        
        const form = document.getElementById('chatForm');
        form.before(indicator);
    }

    function showReplyIndicator(authorName, content) {
        const indicator = document.createElement('div');
        indicator.id = 'reply-indicator';
        indicator.className = 'alert alert-secondary d-flex align-items-center';
        indicator.innerHTML = `
            <i class="bi-reply me-2"></i>
            <div>
                <strong>${authorName}:</strong>
                ${escapeHtml(content.substring(0, 50))}...
            </div>
            <button type="button" class="btn-close ms-auto" onclick="cancelReply()"></button>
        `;
        
        const form = document.getElementById('chatForm');
        form.before(indicator);
    }

    window.cancelEdit = function() {
        state.editingMessageId = null;
        document.getElementById('editing-indicator')?.remove();
        document.getElementById('id_content').value = '';
    };

    window.cancelReply = function() {
        state.replyToMessageId = null;
        document.getElementById('reply-indicator')?.remove();
    };

    function showTypingIndicator(userName) {
        const indicator = document.getElementById('typing');
        indicator.textContent = `${userName} печатает…`;
        indicator.classList.remove('d-none');
    }

    function hideTypingIndicator() {
        const indicator = document.getElementById('typing');
        indicator.classList.add('d-none');
    }

    // ==================== Form Handling ====================

    const form = document.getElementById('chatForm');
    const textarea = document.getElementById('id_content');

    form?.addEventListener('submit', function(e) {
        e.preventDefault();
        
        const content = textarea.value.trim();
        if (!content) return;

        if (state.editingMessageId) {
            // Edit message
            sendAction('edit_message', {
                message_id: state.editingMessageId,
                content
            });
            cancelEdit();
        } else if (state.replyToMessageId) {
            // Reply to message
            sendAction('send_message', {
                content,
                reply_to_id: state.replyToMessageId
            });
            cancelReply();
        } else {
            // New message
            sendAction('send_message', { content });
        }

        textarea.value = '';
        sendAction('stop_typing');
    });

    // Typing indicator
    textarea?.addEventListener('input', function() {
        clearTimeout(typingTimeout);
        
        sendAction('typing');
        
        typingTimeout = setTimeout(() => {
            sendAction('stop_typing');
        }, 3000);
    });

    // ==================== Utilities ====================

    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    function scrollToBottom() {
        chatScroll.scrollTop = chatScroll.scrollHeight;
    }

    // ==================== Init ====================

    connectWebSocket();
    scrollToBottom();

    // Scroll button
    const scrollBtn = document.getElementById('scrollBtn');
    scrollBtn?.addEventListener('click', scrollToBottom);

})();
