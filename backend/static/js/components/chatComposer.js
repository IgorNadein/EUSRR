/**
 * ChatComposer.js
 * Отвечает за логику ввода текста, выбора файлов и отправки сообщений.
 * Полностью заменяет стандартную отправку формы.
 */
class ChatComposer {
    constructor(config) {
        this.chatId = config.chatId;
        this.apiEndpoint = config.apiEndpoint || '/api/v1/communications/upload-message/';
        this.csrfToken = this.getCookie('csrftoken');
        
        // DOM Elements
        this.form = document.getElementById('chatForm');
        this.textarea = document.getElementById('id_content');
        this.previewContainer = document.getElementById('attachmentPreview');
        
        // File Inputs
        this.inputs = {
            document: document.getElementById('documentInput'),
            image: document.getElementById('imageInput'),
            camera: document.getElementById('cameraInput'),
            audio: document.getElementById('audioInput')
        };
        
        // Buttons
        this.buttons = {
            document: document.getElementById('attachDocument'),
            image: document.getElementById('attachImage'),
            camera: document.getElementById('attachCamera'),
            audio: document.getElementById('attachAudio'),
            send: this.form?.querySelector('.btn-send')
        };

        // State
        this.selectedFiles = [];
        this.isSubmitting = false;

        this.init();
    }

    init() {
        if (!this.form) {
            console.error('ChatComposer: Form not found');
            return;
        }

        this.bindEvents();
        console.log('ChatComposer: Initialized');
    }

    bindEvents() {
        // 1. Блокировка стандартной отправки
        this.form.addEventListener('submit', (e) => {
            e.preventDefault();
            e.stopPropagation();
            this.handleSubmit();
        });

        // 2. Обработка кнопок вложений
        if (this.buttons.document) this.buttons.document.addEventListener('click', (e) => { e.preventDefault(); this.inputs.document.click(); });
        if (this.buttons.image) this.buttons.image.addEventListener('click', (e) => { e.preventDefault(); this.inputs.image.click(); });
        if (this.buttons.camera) this.buttons.camera.addEventListener('click', (e) => { e.preventDefault(); this.inputs.camera.click(); });
        if (this.buttons.audio) this.buttons.audio.addEventListener('click', (e) => { e.preventDefault(); this.inputs.audio.click(); });

        // 3. Обработка выбора файлов (change event)
        Object.values(this.inputs).forEach(input => {
            if (input) {
                input.addEventListener('change', (e) => this.handleFileSelect(e.target.files));
            }
        });

        // 4. Enter для отправки (если не Shift+Enter)
        this.textarea.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.form.dispatchEvent(new Event('submit'));
            }
        });
    }

    handleFileSelect(files) {
        if (!files || files.length === 0) return;
        
        // Добавляем новые файлы к существующим
        this.selectedFiles = [...this.selectedFiles, ...Array.from(files)];
        
        // Очищаем input, чтобы можно было выбрать тот же файл снова
        Object.values(this.inputs).forEach(input => { if(input) input.value = ''; });
        
        this.updatePreview();
    }

    removeFile(index) {
        this.selectedFiles.splice(index, 1);
        this.updatePreview();
    }

    updatePreview() {
        if (!this.previewContainer) return;

        if (this.selectedFiles.length === 0) {
            this.previewContainer.classList.add('d-none');
            this.previewContainer.innerHTML = '';
            return;
        }

        this.previewContainer.classList.remove('d-none');
        this.previewContainer.innerHTML = '';

        this.selectedFiles.forEach((file, index) => {
            const item = document.createElement('div');
            item.className = 'attachment-item d-flex align-items-center gap-2 p-2 border rounded mb-2 bg-white';
            
            let icon = 'bi-file-earmark';
            if (file.type.startsWith('image/')) icon = 'bi-image';
            else if (file.type.startsWith('video/')) icon = 'bi-camera-video';
            else if (file.type.startsWith('audio/')) icon = 'bi-music-note';
            
            item.innerHTML = `
                <i class="${icon} fs-4 text-primary"></i>
                <div class="flex-grow-1 text-truncate">
                    <div class="fw-semibold text-truncate">${file.name}</div>
                    <div class="small text-secondary">${this.formatFileSize(file.size)}</div>
                </div>
                <button type="button" class="btn btn-sm btn-ghost text-danger remove-file-btn">
                    <i class="bi-x-lg"></i>
                </button>
            `;

            item.querySelector('.remove-file-btn').addEventListener('click', () => this.removeFile(index));
            this.previewContainer.appendChild(item);
        });
    }

    async handleSubmit() {
        if (this.isSubmitting) return;

        const content = this.textarea.value.trim();
        
        // Валидация
        if (!content && this.selectedFiles.length === 0) {
            // Можно добавить визуальный эффект ошибки
            this.textarea.focus();
            return;
        }

        this.isSubmitting = true;
        this.toggleLoading(true);

        try {
            const formData = new FormData();
            formData.append('chat_id', this.chatId);
            formData.append('content', content); // Отправляем даже пустой текст

            // Добавляем файлы
            this.selectedFiles.forEach((file, index) => {
                formData.append(`file_${index}`, file);
            });

            console.log(`ChatComposer: Sending message. Content len: ${content.length}, Files: ${this.selectedFiles.length}`);

            const response = await fetch(this.apiEndpoint, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': this.csrfToken
                },
                body: formData
            });

            const result = await response.json();

            if (response.ok && result.ok) {
                this.resetForm();
            } else {
                console.error('ChatComposer: Server error', result);
                alert('Ошибка отправки: ' + (result.error || 'Неизвестная ошибка'));
            }

        } catch (error) {
            console.error('ChatComposer: Network error', error);
            alert('Ошибка сети. Проверьте подключение.');
        } finally {
            this.isSubmitting = false;
            this.toggleLoading(false);
            this.textarea.focus();
        }
    }

    resetForm() {
        this.textarea.value = '';
        this.selectedFiles = [];
        this.updatePreview();
        
        // Сброс высоты textarea (если используется авто-высота)
        this.textarea.style.height = 'auto';
    }

    toggleLoading(isLoading) {
        if (this.buttons.send) {
            this.buttons.send.disabled = isLoading;
            this.buttons.send.innerHTML = isLoading 
                ? '<span class="spinner-border spinner-border-sm"></span>' 
                : '<i class="bi-send-fill"></i>';
        }
    }

    formatFileSize(bytes) {
        if (bytes < 1024) return bytes + ' B';
        if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
        return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
    }

    getCookie(name) {
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }
}

// Экспорт для использования
window.ChatComposer = ChatComposer;
