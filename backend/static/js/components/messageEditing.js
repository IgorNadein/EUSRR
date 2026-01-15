/**
 * messageEditing.js
 * 
 * Обработка событий редактирования сообщений через WebSocket.
 * Обновляет DOM когда сообщение было отредактировано другим пользователем
 * или в другой вкладке.
 */

import { MessageRendererV2 } from '../renderers/messageRendererV2.js';

/**
 * Инициализация обработки редактирования сообщений
 */
export function initMessageEditing() {
	console.log('[MessageEditing] Initializing message editing handler...');

	// Слушаем событие редактирования от WebSocket
	window.addEventListener('chat:message-edited', handleMessageEdited);
	
	console.log('[MessageEditing] Handler initialized successfully');
}

/**
 * Обработчик события редактирования сообщения
 * @param {CustomEvent} event - событие с данными отредактированного сообщения
 */
function handleMessageEdited(event) {
	const data = event.detail;
	console.log('[MessageEditing] Message edited event received:', data);

	const message = data.payload || data.message;
	if (!message || !message.id) {
		console.warn('[MessageEditing] Invalid message data:', data);
		return;
	}

	// Подробный лог того что пришло
	console.log('[MessageEditing] ========== MESSAGE DATA ==========');
	console.log('[MessageEditing] ID:', message.id);
	console.log('[MessageEditing] Content:', message.content);
	console.log('[MessageEditing] has_attachments:', message.has_attachments);
	console.log('[MessageEditing] attachments:', message.attachments);
	console.log('[MessageEditing] attachments length:', message.attachments?.length);
	console.log('[MessageEditing] reply_to:', message.reply_to);
	console.log('[MessageEditing] poll:', message.poll);
	console.log('[MessageEditing] is_forwarded:', message.is_forwarded);
	console.log('[MessageEditing] forwarded_from:', message.forwarded_from);
	console.log('[MessageEditing] reactions_summary:', message.reactions_summary);
	console.log('[MessageEditing] is_edited:', message.is_edited);
	console.log('[MessageEditing] ===================================');

	updateMessageInDOM(message);
}

/**
 * Обновляет сообщение в DOM после редактирования
 * ИСПОЛЬЗУЕТ ПОЛНУЮ ПЕРЕРИСОВКУ через MessageRenderer
 * @param {Object} message - данные сообщения
 */
function updateMessageInDOM(message) {
	// Ищем все элементы с этим message_id (может быть несколько копий)
	const messageElements = document.querySelectorAll(`[data-message-id="${message.id}"]`);
	
	if (messageElements.length === 0) {
		console.log('[MessageEditing] Message element not found in DOM:', message.id);
		return;
	}

	console.log('[MessageEditing] Updating message elements:', messageElements.length);
	console.log('[MessageEditing] Message data:', {
		id: message.id,
		content: message.content,
		has_attachments: message.has_attachments,
		attachments: message.attachments?.length || 0,
		reply_to: !!message.reply_to,
		poll: !!message.poll,
		reactions: Object.keys(message.reactions_summary || {}).length,
		is_edited: message.is_edited
	});

	messageElements.forEach(oldMessageEl => {
		try {
			// Используем существующий renderer из ChatControllerV2
			const renderer = window.chatController?.messageRenderer;
			
			if (!renderer) {
				console.error('[MessageEditing] MessageRenderer not available from ChatController');
				return;
			}

			// Рендерим сообщение через существующий renderer (возвращает DOM элемент)
			const newMessageEl = renderer.renderSingleMessage(message);
			
			if (!newMessageEl) {
				console.error('[MessageEditing] Failed to render new message element');
				return;
			}
			
			console.log('[MessageEditing] Generated element:', {
				tagName: newMessageEl.tagName,
				className: newMessageEl.className,
				hasContent: !!newMessageEl.querySelector('.message-content'),
				hasAttachments: !!newMessageEl.querySelector('.message-attachments')
			});

			// Сохраняем позицию скролла
			const scrollContainer = document.getElementById('chatScroll');
			const shouldMaintainScroll = scrollContainer && (
				scrollContainer.scrollHeight - scrollContainer.scrollTop - scrollContainer.clientHeight > 100
			);
			const scrollBefore = scrollContainer?.scrollTop || 0;

			// Заменяем элемент
			oldMessageEl.replaceWith(newMessageEl);
			console.log('[MessageEditing] ✓ Message DOM replaced');

			// Восстанавливаем скролл если пользователь не внизу
			if (shouldMaintainScroll && scrollContainer) {
				scrollContainer.scrollTop = scrollBefore;
			}

			// Переинициализируем компоненты для нового элемента
			const currentUserId = renderer.currentUserId;
			reinitMessageComponents(newMessageEl, message.id, currentUserId);

		} catch (error) {
			console.error('[MessageEditing] Error updating message:', error);
		}
	});

	console.log('[MessageEditing] ✓ Message fully updated with all components:', message.id);
}

/**
 * Переинициализирует компоненты сообщения после замены DOM
 * @param {HTMLElement} messageEl - элемент сообщения
 * @param {number} messageId - ID сообщения
 * @param {number} currentUserId - ID текущего пользователя
 */
function reinitMessageComponents(messageEl, messageId, currentUserId) {
	console.log('[MessageEditing] Reinitializing components for message:', messageId);

	// 1. Реинициализируем реакции
	if (window.reactions && typeof window.reactions.initMessageReactions === 'function') {
		try {
			window.reactions.initMessageReactions(messageEl, messageId, currentUserId);
			console.log('[MessageEditing] ✓ Reactions reinitialized');
		} catch (error) {
			console.error('[MessageEditing] Failed to reinit reactions:', error);
		}
	}

	// 2. Контекстное меню работает через делегирование событий, 
	//    переинициализация не требуется

	// 3. Lightbox для изображений (если используется)
	const images = messageEl.querySelectorAll('img[data-lightbox], .attachment-image');
	if (images.length > 0 && window.initLightbox) {
		try {
			window.initLightbox(messageEl);
			console.log('[MessageEditing] ✓ Lightbox reinitialized for', images.length, 'images');
		} catch (error) {
			console.error('[MessageEditing] Failed to reinit lightbox:', error);
		}
	}

	// 4. Голосования (если есть)
	const pollEl = messageEl.querySelector('[data-poll-id]');
	if (pollEl && window.chatPoll) {
		try {
			const pollId = pollEl.dataset.pollId;
			console.log('[MessageEditing] Refreshing poll:', pollId);
			// Вызываем refreshPoll для обновления состояния опроса
			window.chatPoll.refreshPoll(pollId, pollEl);
			console.log('[MessageEditing] ✓ Poll reinitialized, id:', pollId);
		} catch (error) {
			console.error('[MessageEditing] Failed to reinit poll:', error);
		}
	}

	// 5. Обработчики кликов на reply-reference (скролл к сообщению)
	const replyRef = messageEl.querySelector('.reply-reference');
	if (replyRef) {
		// Уже обработано через onclick в HTML, но можно добавить дополнительную логику
		console.log('[MessageEditing] ✓ Reply reference detected');
	}

	console.log('[MessageEditing] ✓ All components reinitialized');
}

/**
 * Очистка обработчика (для случаев когда нужно отключить)
 */
export function cleanupMessageEditing() {
	window.removeEventListener('chat:message-edited', handleMessageEdited);
	console.log('[MessageEditing] Handler cleaned up');
}
