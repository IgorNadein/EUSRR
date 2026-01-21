import { createMessageElement } from './chatMessageTemplates.js';

/**
 * Chat Composer module
 * Отвечает за ввод текста, прикрепление файлов и отправку сообщений через REST API.
 * 
 * РЕФАКТОРИНГ: Теперь использует MessageRenderer для создания pending сообщений
 */

const DEFAULT_CONFIG = {
	selector: '[data-chat-composer]',
	textareaSelector: '#id_content',
	previewSelector: '#attachmentPreview',
	inputs: {
		document: '#documentInput',
		image: '#imageInput',
		camera: '#cameraInput',
		audio: '#audioInput'
	},
	submitSelector: '.btn-send',
	uploadUrl: '/api/v1/communications/messages/upload/',
	csrfCookieName: 'csrftoken',
	scrollSelector: '#chatScroll',
	profileUrl: '/employees/profile/',
	detailUrlTemplate: '/employees/0/'
};

const ICON_BY_MIME = [
	{ test: (mime) => mime.startsWith('image/'), icon: 'bi-image text-success' },
	{ test: (mime) => mime.startsWith('video/'), icon: 'bi-camera-video text-info' },
	{ test: (mime) => mime.startsWith('audio/'), icon: 'bi-mic text-danger' },
	{ test: (mime) => mime.includes('pdf'), icon: 'bi-file-pdf text-primary' }
];

class ChatComposer {
	constructor(form, options = {}) {
		console.log('[ChatComposer] Constructor called with form:', form, 'options:', options);
		
		this.form = form;
		this.options = { ...DEFAULT_CONFIG, ...options };
		this.chatId = Number(options.chatId || form.dataset.chatId || 0);
		this.uploadUrl = options.uploadUrl || form.dataset.uploadUrl || DEFAULT_CONFIG.uploadUrl;
		this.textarea = form.querySelector(this.options.textareaSelector);
		this.preview = form.querySelector(this.options.previewSelector) || document.querySelector(this.options.previewSelector);
		this.inputs = this.resolveInputs();
		this.submitButton = form.querySelector(this.options.submitSelector);
		this.csrfCookieName = this.options.csrfCookieName;
		this.scrollEl = document.querySelector(this.options.scrollSelector);
		this.meId = Number(options.meId || form.dataset.meId || this.scrollEl?.dataset.meId || 0);
		this.meName = options.meName || form.dataset.meName || 'Вы';
		this.meAvatar = options.meAvatar || form.dataset.meAvatar || this.scrollEl?.dataset.meAvatar || '';
		this.profileUrl = options.profileUrl || form.dataset.profileUrl || this.options.profileUrl;
		this.detailUrlTemplate = options.detailUrlTemplate || form.dataset.detailUrlTemplate || this.options.detailUrlTemplate;
		this.messageRenderer = options.messageRenderer || null; // DEPRECATED: Старый MessageRenderer
		this.chatController = options.chatController || null; // НОВОЕ: ChatController для новой архитектуры
		this.selectedFiles = [];
		this.typingThrottle = 1200;
		this.lastTypingSent = 0;
		this.isSubmitting = false;
		this.pendingQueue = [];
		this.boundMessageHandler = (event) => this.handleIncomingMessage(event);

		if (!this.chatId) {
			console.warn('ChatComposer: chatId is missing');
			return;
		}

		this.bindEvents();
		this.bindEmojiPicker();
		form.dataset.composerBound = '1';
	}

	resolveInputs() {
		const resolved = {};
		Object.entries(this.options.inputs || {}).forEach(([key, selector]) => {
			resolved[key] = document.querySelector(selector);
		});
		return resolved;
	}

	bindEvents() {
		console.log('[ChatComposer] bindEvents: attaching handlers', this.form);
		
		// Обработка submit формы
		this.form.addEventListener('submit', (e) => {
			console.log('[ChatComposer] FORM SUBMIT EVENT!');
			e.preventDefault(); // На всякий случай
			this.handleSubmit(e);
		});

		['document', 'image', 'camera', 'audio'].forEach((type) => {
			const btn = document.getElementById(`attach${capitalize(type)}`);
			const input = this.inputs[type];
			if (btn && input) {
				btn.addEventListener('click', (event) => {
					event.preventDefault();
					input.click();
				});
				input.addEventListener('change', (event) => this.handleFileSelect(event));
			}
		});

		if (this.textarea) {
			this.textarea.addEventListener('input', () => {
				this.handleTyping();
			});
			
			// Обработка вставки из буфера обмена
			this.textarea.addEventListener('paste', (e) => {
				this.handlePaste(e);
			});
			
			// Обработка drag-and-drop
			this.textarea.addEventListener('dragover', (e) => {
				e.preventDefault();
				e.stopPropagation();
				this.textarea.classList.add('drag-over');
			});
			
			this.textarea.addEventListener('dragleave', (e) => {
				e.preventDefault();
				e.stopPropagation();
				this.textarea.classList.remove('drag-over');
			});
			
			this.textarea.addEventListener('drop', (e) => {
				e.preventDefault();
				e.stopPropagation();
				this.textarea.classList.remove('drag-over');
				this.handleDrop(e);
			});
		}

		window.addEventListener('chat:message-received', this.boundMessageHandler);
	}

	bindEmojiPicker() {
		// Новый emoji-picker-element
		const picker = this.form.querySelector('[data-emoji-picker]');
		if (picker) {
			picker.addEventListener('emoji-click', (event) => {
				event.preventDefault();
				const emoji = event.detail?.unicode;
				if (emoji) {
					this.insertEmoji(emoji);
				}
			});

			// Предотвращаем закрытие dropdown при клике внутри emoji-picker
			const emojiDropdown = picker.closest('.dropdown-menu');
			if (emojiDropdown) {
				emojiDropdown.addEventListener('click', (event) => {
					event.stopPropagation();
				});
			}
		}
	}

	insertEmoji(emoji) {
		if (!this.textarea) return;
		const textarea = this.textarea;
		const start = textarea.selectionStart ?? textarea.value.length;
		const end = textarea.selectionEnd ?? textarea.value.length;
		const value = textarea.value || '';
		const emojiText = typeof emoji === 'string' ? emoji : emoji.emoji || emoji.unicode || emoji;
		textarea.value = `${value.slice(0, start)}${emojiText}${value.slice(end)}`;
		const caret = start + emojiText.length;
		textarea.focus();
		textarea.setSelectionRange?.(caret, caret);
		textarea.dispatchEvent(new Event('input', { bubbles: true }));
	}

	handleFileSelect(event) {
		const files = Array.from(event.target.files || []);
		if (!files.length) return;

			files.forEach((file) => {
				const uuidSupported = window.crypto && typeof window.crypto.randomUUID === 'function';
				const fileId = uuidSupported ? window.crypto.randomUUID() : `${Date.now()}-${Math.random()}`;
				this.selectedFiles.push({ id: fileId, file });
			});

		event.target.value = '';
		this.renderPreview();
	}

	/**
	 * Обработка вставки из буфера обмена
	 * Поддерживает вставку изображений и файлов
	 */
	handlePaste(event) {
		const clipboardData = event.clipboardData || window.clipboardData;
		if (!clipboardData) return;

		const items = Array.from(clipboardData.items || []);
		const files = Array.from(clipboardData.files || []);
		
		// Проверяем наличие файлов
		let hasFiles = false;
		const pastedFiles = [];

		// Сначала проверяем items (более надежный способ)
		items.forEach((item) => {
			if (item.kind === 'file') {
				const file = item.getAsFile();
				if (file) {
					pastedFiles.push(file);
					hasFiles = true;
				}
			}
		});

		// Если не нашли через items, пробуем files
		if (!hasFiles && files.length > 0) {
			pastedFiles.push(...files);
			hasFiles = true;
		}

		// Если есть файлы - обрабатываем их
		if (hasFiles && pastedFiles.length > 0) {
			console.log('[ChatComposer] Pasted files:', pastedFiles);
			
			// Предотвращаем вставку текста/HTML если вставлены файлы
			event.preventDefault();
			
			// Добавляем файлы в selectedFiles
			pastedFiles.forEach((file) => {
				const uuidSupported = window.crypto && typeof window.crypto.randomUUID === 'function';
				const fileId = uuidSupported ? window.crypto.randomUUID() : `${Date.now()}-${Math.random()}`;
				this.selectedFiles.push({ id: fileId, file });
			});

			// Обновляем превью
			this.renderPreview();

			// Показываем уведомление пользователю
			const fileCount = pastedFiles.length;
			const fileWord = fileCount === 1 ? 'файл' : fileCount < 5 ? 'файла' : 'файлов';
			console.log(`[ChatComposer] Добавлено ${fileCount} ${fileWord} из буфера обмена`);
		}
		// Если файлов нет - оставляем стандартное поведение (вставка текста)
	}

	/**
	 * Обработка перетаскивания файлов (drag-and-drop)
	 */
	handleDrop(event) {
		const dataTransfer = event.dataTransfer;
		if (!dataTransfer) return;

		const files = Array.from(dataTransfer.files || []);
		
		if (files.length > 0) {
			console.log('[ChatComposer] Dropped files:', files);
			
			// Добавляем файлы в selectedFiles
			files.forEach((file) => {
				const uuidSupported = window.crypto && typeof window.crypto.randomUUID === 'function';
				const fileId = uuidSupported ? window.crypto.randomUUID() : `${Date.now()}-${Math.random()}`;
				this.selectedFiles.push({ id: fileId, file });
			});

			// Обновляем превью
			this.renderPreview();

			// Показываем уведомление пользователю
			const fileCount = files.length;
			const fileWord = fileCount === 1 ? 'файл' : fileCount < 5 ? 'файла' : 'файлов';
			console.log(`[ChatComposer] Добавлено ${fileCount} ${fileWord} перетаскиванием`);
		}
	}

	handleTyping() {
		const now = Date.now();
		if (now - this.lastTypingSent > this.typingThrottle) {
			this.lastTypingSent = now;
			if (window.chatWebSocketApi?.sendTyping) {
				window.chatWebSocketApi.sendTyping();
			}
		}
	}

	/**
	 * ЕДИНОЕ место обработки формы
	 * Обрабатывает ВСЕ типы отправки: send, reply, edit
	 * Определяет режим через chatFormManager
	 */
	async handleSubmit(event) {
		console.log('[ChatComposer] handleSubmit called');
		
		const content = (this.textarea?.value || '').trim();
		
		// Получаем данные из formManager
		const formData = window.chatFormManager?.getFormData() || { mode: 'send' };
		const mode = formData.mode;
		const messageId = formData.editMessageId || null;
		const replyToMessageId = formData.replyToMessageId || null;
		
		// Валидация: проверяем что есть хоть что-то
		const hasContent = content.length > 0;
		const hasFiles = this.selectedFiles.length > 0;
		
		if (!hasContent && !hasFiles) {
			console.warn('[ChatComposer] Cannot send empty message');
			alert('Сообщение должно содержать либо текст, либо вложения');
			return;
		}
		
		console.log('[ChatComposer] Mode:', mode, 'EditId:', messageId, 'ReplyTo:', replyToMessageId, 'Content:', content.substring(0, 50), 'Files:', hasFiles);
		
		// Блокируем повторную отправку
		if (this.isSubmitting) {
			console.log('[ChatComposer] Already submitting, skipping');
			return;
		}
		
		try {
			this.isSubmitting = true;
			this.setLoading(true);
			
			// EDIT: отправляем на отдельный endpoint
			if (mode === 'edit' && messageId) {
				await this.sendEdit(messageId, content);
			}
			// SEND или REPLY: отправляем на upload-message
			else {
				await this.sendMessage(content, replyToMessageId);
			}
			
		} catch (error) {
			console.error('[ChatComposer] Send failed', error);
			alert(error.message || 'Ошибка при отправке сообщения');
		} finally {
			this.isSubmitting = false;
			this.setLoading(false);
		}
	}
	
	/**
	 * Отправка нового сообщения или ответа
	 * @param {string} content - Текст сообщения
	 * @param {number|null} replyToMessageId - ID сообщения на которое отвечаем
	 */
	async sendMessage(content, replyToMessageId = null) {
		const formData = new FormData(this.form);
		
		// Добавляем файлы из this.selectedFiles
		this.selectedFiles.forEach((entry, index) => {
			formData.append(`file_${index}`, entry.file, entry.file.name);
		});
		
		// Если content не попал в FormData, добавляем вручную
		if (!formData.has('content') && content) {
			formData.set('content', content);
		}
		
		// Добавляем reply_to если это ответ
		if (replyToMessageId) {
			formData.set('reply_to', replyToMessageId);
			console.log('[ChatComposer] Sending reply to message:', replyToMessageId);
		}
		
		// Проверяем chat_id
		if (!formData.has('chat_id')) {
			console.error('[ChatComposer] chat_id missing!');
			formData.set('chat_id', this.chatId);
		}
		
		// Определяем URL для отправки
		const url = this.form.action || this.uploadUrl;
		
		const response = await fetch(url, {
			method: 'POST',
			body: formData
		});
		
		// Проверяем критичные ошибки
		if (response.status === 403 || response.status === 400) {
			const data = await response.json().catch(() => ({}));
			throw new Error(data.error || 'Ошибка отправки');
		}
		
		// Успех - очищаем форму
		this.resetForm();
		
		// Сбрасываем formManager
		if (window.chatFormManager) {
			window.chatFormManager.setModeToSend();
		}
	}
	
	/**
	 * Редактирование существующего сообщения
	 * Поддерживает загрузку новых файлов
	 */
	async sendEdit(messageId, content) {
		const csrfToken = getCookie(this.csrfCookieName);
		if (!csrfToken) {
			throw new Error('CSRF токен не найден');
		}
		
		// Разделяем файлы на существующие и новые
		const existingAttachmentIds = [];
		const newFiles = [];
		
		this.selectedFiles.forEach(entry => {
			if (entry.file._isExisting === true && entry.file._existingId) {
				// Существующее вложение - сохраняем его ID
				existingAttachmentIds.push(entry.file._existingId);
			} else {
				// Новый файл - нужно загрузить
				newFiles.push(entry);
			}
		});
		
		console.log('[ChatComposer] Editing message:', {
			messageId,
			contentLength: content.length,
			existingAttachments: existingAttachmentIds,
			newFiles: newFiles.length
		});
		
		// Шаг 1: Загружаем новые файлы если есть
		const newAttachmentIds = [];
		if (newFiles.length > 0) {
			console.log('[ChatComposer] Uploading new files:', newFiles.length);
			
			const formData = new FormData();
			
			newFiles.forEach((entry, index) => {
				formData.append(`file_${index}`, entry.file, entry.file.name);
			});
			
			// Загружаем файлы через временный endpoint (без создания сообщения)
			const uploadResponse = await fetch('/api/v1/communications/messages/upload-temp/', {
				method: 'POST',
				headers: {
					'X-CSRFToken': csrfToken
				},
				body: formData
			});
			
			if (!uploadResponse.ok) {
				const data = await uploadResponse.json().catch(() => ({}));
				throw new Error(data.error || 'Ошибка загрузки файлов');
			}
			
			const uploadData = await uploadResponse.json();
			
			// Получаем ID вложений без привязки к сообщению
			if (uploadData.attachment_ids) {
				newAttachmentIds.push(...uploadData.attachment_ids);
				console.log('[ChatComposer] New attachments uploaded:', newAttachmentIds);
			}
		}
		
		// Шаг 2: Собираем все ID вложений (существующие + новые)
		const allAttachmentIds = [...existingAttachmentIds, ...newAttachmentIds];
		
		console.log('[ChatComposer] All attachment IDs:', allAttachmentIds);
		
		// Шаг 3: Отправляем запрос на редактирование
		const editUrl = `/api/v1/communications/messages/${messageId}/`;
		
		const response = await fetch(editUrl, {
			method: 'PATCH',
			headers: {
				'Content-Type': 'application/json',
				'X-CSRFToken': csrfToken
			},
			body: JSON.stringify({ 
				content,
				existing_attachment_ids: allAttachmentIds.length > 0 ? allAttachmentIds : []
			})
		});
		
		console.log('[ChatComposer] Edit response:', response.status);
		
		if (!response.ok) {
			const data = await response.json().catch(() => ({}));
			throw new Error(data.error || data.detail || 'Ошибка редактирования');
		}
		
		// Успех - очищаем форму
		this.resetForm();
		
		// Сбрасываем formManager
		if (window.chatFormManager) {
			window.chatFormManager.setModeToSend();
		}
		
		console.log('[ChatComposer] Message edited successfully');
	}

	/**
	 * Редактирование существующего сообщения
	 */
	async editMessage(messageId, newContent) {
		const csrfToken = getCookie(this.csrfCookieName);
		if (!csrfToken) {
			alert('CSRF токен не найден. Обновите страницу.');
			return;
		}

		try {
			this.setLoading(true);
			
			const response = await fetch(`/api/v1/communications/messages/${messageId}/`, {
				method: 'PATCH',
				headers: {
					'Content-Type': 'application/json',
					'X-CSRFToken': csrfToken
				},
				body: JSON.stringify({ content: newContent })
			});

			const payload = await response.json().catch(() => ({}));

			if (!response.ok) {
				const errorMessage = payload.error || payload.detail || 'Не удалось отредактировать сообщение';
				throw new Error(errorMessage);
			}

			// Очищаем форму и индикаторы
			this.resetForm();
			this.clearEditMode();
			
			// Сбрасываем formManager если доступен
			if (window.chatFormManager) {
				window.chatFormManager.setModeToSend();
			}
			
		} catch (error) {
			console.error('ChatComposer: edit failed', error);
			alert(error.message || 'Ошибка при редактировании сообщения');
		} finally {
			this.setLoading(false);
		}
	}

	async sendViaHTTP(content, files, replyToMessageId = null) {
		const csrfToken = getCookie(this.csrfCookieName);
		if (!csrfToken) {
			alert('CSRF токен не найден. Обновите страницу.');
			return;
		}

		const formData = new FormData();
		formData.append('chat_id', this.chatId);
		formData.append('content', content || ''); // Может быть пустым если только файлы
		
		// Добавляем reply_to если это ответ на сообщение
		if (replyToMessageId) {
			formData.append('reply_to', replyToMessageId);
		}
		
		files.forEach((entry, index) => {
			formData.append(`file_${index}`, entry.file, entry.file.name);
		});

		const shouldShowPending = files.length > 0 && this.scrollEl;
		let pendingId = null;
		if (shouldShowPending) {
			pendingId = this.renderPendingMessage(content);
		}

		try {
			this.setLoading(true);
			const response = await fetch(this.uploadUrl, {
				method: 'POST',
				body: formData,
				headers: {
					'X-CSRFToken': csrfToken
				}
			});

			const payload = await response.json().catch(() => ({}));

			if (!response.ok || !payload.ok) {
				const errorMessage = payload.error || 'Не удалось отправить сообщение';
				throw new Error(errorMessage);
			}

			this.resetForm();
			
			// Сбрасываем formManager если доступен (для режима reply)
			if (window.chatFormManager && window.chatFormManager.getMode() !== 'send') {
				window.chatFormManager.setModeToSend();
			}
			
		} catch (error) {
			console.error('ChatComposer: submit failed', error);
			alert(error.message || 'Ошибка при отправке сообщения');
			if (pendingId) {
				this.removePendingMessage(pendingId);
			}
		} finally {
			this.setLoading(false);
		}
	}

	renderPendingMessage(content) {
		if (!this.scrollEl) return null;
		const pendingId = (window.crypto?.randomUUID?.() || `pending-${Date.now()}-${Math.random()}`).toString();
		const attachments = this.selectedFiles.map((entry) => {
			const objectUrl = URL.createObjectURL(entry.file);
			return {
				id: entry.id,
				file_name: entry.file.name,
				file_type: detectFileType(entry.file.type),
				file_url: objectUrl,
				file_size: entry.file.size,
				mime_type: entry.file.type
			};
		});

		const msg = {
			id: pendingId,
			author_id: this.meId,
			author_name: this.meName,
			author_url: this.profileUrl,
			avatar: this.meAvatar,
			content,
			created_ts: Date.now(),
			has_attachments: attachments.length > 0,
			attachments,
			is_pending: true
		};

		// НОВАЯ АРХИТЕКТУРА: Используем ChatController для оптимистичных сообщений
		// ChatController сам создаст pending message и добавит в Store
		if (this.chatController) {
			const tempId = this.chatController.sendMessage(content, {
				attachments,
				optimistic: true
			});
			
			this.pendingQueue.push({
				id: pendingId,
				tempId: tempId, // ID от ChatController
				objectUrls: attachments.map((att) => att.file_url)
			});
			
			return pendingId;
		}
		
		// FALLBACK: Старая логика с MessageRenderer (для backward compatibility)
		let element;
		if (this.messageRenderer) {
			element = this.messageRenderer.createMessageElement(msg, true); // true = isPending
		} else {
			// Fallback для обратной совместимости
			element = createMessageElement(msg, {
				meId: this.meId,
				profileUrl: this.profileUrl,
				detailUrlTemplate: this.detailUrlTemplate
			});
		}
		
		element.dataset.pendingId = pendingId;
		this.scrollEl.appendChild(element);
		this.scrollEl.scrollTop = this.scrollEl.scrollHeight;

		this.pendingQueue.push({
			id: pendingId,
			element,
			objectUrls: attachments.map((att) => att.file_url)
		});
		return pendingId;
	}

	handleIncomingMessage(event) {
		const msg = event?.detail;
		if (!msg) return;
		if (Number(msg.chat_id || this.chatId) !== Number(this.chatId)) return;
		if (Number(msg.author_id) !== Number(this.meId)) return;
		this.resolvePendingMessage();
	}

	resolvePendingMessage() {
		const pending = this.pendingQueue.shift();
		if (!pending) return;
		pending.objectUrls.forEach((url) => URL.revokeObjectURL(url));
		if (pending.element) {
			pending.element.classList.add('message-pending--resolved');
			pending.element.remove();
		}
	}

	removePendingMessage(pendingId) {
		const index = this.pendingQueue.findIndex((item) => item.id === pendingId);
		if (index === -1) return;
		const [pending] = this.pendingQueue.splice(index, 1);
		pending.objectUrls.forEach((url) => URL.revokeObjectURL(url));
		pending.element?.remove();
	}

	renderPreview() {
		if (!this.preview) return;

		if (this.selectedFiles.length === 0) {
			this.preview.classList.add('d-none');
			this.preview.innerHTML = '';
			return;
		}

		this.preview.classList.remove('d-none');
		this.preview.innerHTML = '';

		this.selectedFiles.forEach((entry) => {
			const isImage = entry.file.type.startsWith('image/');
			const isExisting = entry.file._isExisting === true;
			const iconClass = pickIcon(entry.file.type);
			const wrapper = document.createElement('div');
			wrapper.className = 'attachment-item d-flex align-items-center gap-2 p-2 rounded mb-2';
			
			// Определяем URL изображения
			let imgUrl = null;
			if (isImage) {
				if (isExisting && entry.file._existingUrl) {
					// Для существующих файлов используем их URL
					imgUrl = entry.file._existingUrl;
				} else {
					// Для новых файлов создаем blob URL
					imgUrl = URL.createObjectURL(entry.file);
				}
			}
			
			// Определяем размер файла
			const fileSizeStr = isExisting && entry.file._sizeStr 
				? entry.file._sizeStr 
				: formatFileSize(entry.file.size);
			
			// Для изображений показываем превью
			if (isImage && imgUrl) {
				wrapper.innerHTML = `
					<img src="${imgUrl}" alt="${entry.file.name}" 
					     style="max-width: 60px; max-height: 60px; border-radius: 6px; object-fit: cover;" />
					<div class="flex-grow-1">
						<div class="fw-semibold text-truncate">${entry.file.name}</div>
						<div class="small text-secondary">${fileSizeStr}</div>
					</div>
					<button type="button" class="btn btn-sm btn-ghost" aria-label="Удалить файл" data-file-id="${entry.id}">
						<i class="bi-x-lg"></i>
					</button>
				`;
			} else {
				// Для других файлов - иконка
				wrapper.innerHTML = `
					<i class="${iconClass} fs-4"></i>
					<div class="flex-grow-1">
						<div class="fw-semibold text-truncate">${entry.file.name}</div>
						<div class="small text-secondary">${fileSizeStr}</div>
					</div>
					<button type="button" class="btn btn-sm btn-ghost" aria-label="Удалить файл" data-file-id="${entry.id}">
						<i class="bi-x-lg"></i>
					</button>
				`;
			}

			wrapper.querySelector('button')?.addEventListener('click', () => {
				this.removeFile(entry.id);
				// Очищаем URL.createObjectURL только для НОВЫХ изображений
				if (isImage && !isExisting && imgUrl) {
					URL.revokeObjectURL(imgUrl);
				}
			});

			this.preview.appendChild(wrapper);
		});
	}

	removeFile(entryId) {
		this.selectedFiles = this.selectedFiles.filter((entry) => entry.id !== entryId);
		this.renderPreview();
	}

	resetForm() {
		if (this.textarea) {
			this.textarea.value = '';
			this.textarea.dispatchEvent(new Event('input'));
		}

		Object.values(this.inputs).forEach((input) => {
			if (input) input.value = '';
		});

		this.selectedFiles = [];
		this.renderPreview();
		
		// Очищаем индикаторы reply и edit
		this.clearReplyMode();
		this.clearEditMode();
	}
	
	/**
	 * Очистка режима ответа
	 */
	clearReplyMode() {
		const replyIndicator = document.querySelector('.reply-composer-indicator');
		if (replyIndicator) {
			replyIndicator.remove();
		}
	}
	
	/**
	 * Очистка режима редактирования
	 */
	clearEditMode() {
		const editIndicator = document.querySelector('.edit-indicator');
		if (editIndicator) {
			editIndicator.remove();
		}
		if (this.textarea) {
			delete this.textarea.dataset.editingMessageId;
		}
	}

	setLoading(state) {
		this.isSubmitting = state;
		if (!this.submitButton) return;
		this.submitButton.disabled = state;
		this.submitButton.setAttribute('aria-busy', state ? 'true' : 'false');
	}
}

function formatFileSize(bytes) {
	if (!Number.isFinite(bytes)) return '';
	if (bytes < 1024) return `${bytes} Б`;
	if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} КБ`;
	if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} МБ`;
	return `${(bytes / (1024 * 1024 * 1024)).toFixed(1)} ГБ`;
}

function getCookie(name) {
	const cookies = document.cookie ? document.cookie.split(';') : [];
	for (const cookie of cookies) {
		const trimmed = cookie.trim();
		if (trimmed.startsWith(`${name}=`)) {
			return decodeURIComponent(trimmed.substring(name.length + 1));
		}
	}
	return null;
}

function pickIcon(mime = '') {
	const match = ICON_BY_MIME.find((item) => item.test(mime));
	return match ? match.icon : 'bi-file-earmark text-primary';
}

function capitalize(text = '') {
	return text.charAt(0).toUpperCase() + text.slice(1);
}

function detectFileType(mime = '') {
	if (!mime) return 'file';
	if (mime.startsWith('image/')) return 'image';
	if (mime.startsWith('video/')) return 'video';
	if (mime.startsWith('audio/')) return 'audio';
	return 'file';
}

/**
 * Инициализация композера для форм на странице
 * @param {Object} config - Конфигурация
 * @returns {Array<ChatComposer>} Массив инстансов композеров
 */
export function initChatComposer(config = {}) {
	const forms = document.querySelectorAll(config.selector || DEFAULT_CONFIG.selector);
	const instances = [];

	forms.forEach((form) => {
		if (form.dataset.composerBound === '1') return;
		const instance = new ChatComposer(form, {
			...config,
			chatId: config.chatId || form.dataset.chatId,
			uploadUrl: config.uploadUrl || form.dataset.uploadUrl
		});
		if (instance.form) {
			instances.push(instance);
		}
	});

	// Возвращаем первый инстанс или массив
	return instances.length === 1 ? instances[0] : instances;
}

// УДАЛЕНО: Авто-инициализация теперь происходит через chat_detail_scripts.html
// if (document.readyState === 'loading') {
// 	document.addEventListener('DOMContentLoaded', () => initChatComposer());
// } else {
// 	initChatComposer();
// }
