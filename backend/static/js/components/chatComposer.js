import { createMessageElement } from './chatMessageTemplates.js';

/**
 * Chat Composer module
 * Отвечает за ввод текста, прикрепление файлов и отправку сообщений через REST API.
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
	uploadUrl: '/api/v1/communications/upload-message/',
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
		this.form.addEventListener('submit', (e) => this.handleSubmit(e));

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

	handleTyping() {
		const now = Date.now();
		if (now - this.lastTypingSent > this.typingThrottle) {
			this.lastTypingSent = now;
			if (window.chatWebSocketApi?.sendTyping) {
				window.chatWebSocketApi.sendTyping();
			}
		}
	}

	async handleSubmit(event) {
		event.preventDefault();
		if (this.isSubmitting) return;

		const content = (this.textarea?.value || '').trim();
		if (!content && this.selectedFiles.length === 0) {
			alert('Введите текст сообщения или прикрепите файл');
			return;
		}

		const csrfToken = getCookie(this.csrfCookieName);
		if (!csrfToken) {
			alert('CSRF токен не найден. Обновите страницу.');
			return;
		}

		const formData = new FormData();
		formData.append('chat_id', this.chatId);
		formData.append('content', content);
		this.selectedFiles.forEach((entry, index) => {
			formData.append(`file_${index}`, entry.file, entry.file.name);
		});

		const shouldShowPending = this.selectedFiles.length > 0 && this.scrollEl;
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

		const element = createMessageElement(msg, {
			meId: this.meId,
			profileUrl: this.profileUrl,
			detailUrlTemplate: this.detailUrlTemplate
		});
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
			const iconClass = pickIcon(entry.file.type);
			const wrapper = document.createElement('div');
			wrapper.className = 'attachment-item d-flex align-items-center gap-2 p-2 rounded mb-2';
			wrapper.innerHTML = `
				<i class="${iconClass} fs-4"></i>
				<div class="flex-grow-1">
					<div class="fw-semibold text-truncate">${entry.file.name}</div>
					<div class="small text-secondary">${formatFileSize(entry.file.size)}</div>
				</div>
				<button type="button" class="btn btn-sm btn-ghost" aria-label="Удалить файл" data-file-id="${entry.id}">
					<i class="bi-x-lg"></i>
				</button>
			`;

			wrapper.querySelector('button')?.addEventListener('click', () => {
				this.removeFile(entry.id);
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

	return instances;
}

if (document.readyState === 'loading') {
	document.addEventListener('DOMContentLoaded', () => initChatComposer());
} else {
	initChatComposer();
}
