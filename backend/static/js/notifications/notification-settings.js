/**
 * Управление настройками уведомлений
 */
class NotificationSettingsManager {
    constructor() {
        this.settings = {};
        this.init();
    }
    
    init() {
        this.loadSettings();
        this.setupSoundToggle();
    }
    
    async loadSettings() {
        const container = document.getElementById('settingsContainer');
        if (!container) return;
        
        try {
            const response = await fetch('/api/notifications/settings/', {
                credentials: 'same-origin',
                headers: {
                    'Accept': 'application/json',
                }
            });
            
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            const data = await response.json();
            this.settings = data.settings || {};
            this.renderSettings();
        } catch (error) {
            console.error('[Settings] Error loading:', error);
            container.innerHTML = `
                <div class="alert alert-danger">
                    <i class="bi-exclamation-triangle"></i>
                    Ошибка загрузки настроек: ${error.message}
                </div>
            `;
        }
    }
    
    renderSettings() {
        const container = document.getElementById('settingsContainer');
        if (!container) return;
        
        const categories = [
            { code: 'communications', name: 'Коммуникации', icon: 'bi-chat-dots', description: 'Сообщения, упоминания, ответы в чатах' },
            { code: 'documents', name: 'Документы', icon: 'bi-file-earmark-text', description: 'Новые документы, ознакомления' },
            { code: 'requests', name: 'Заявления', icon: 'bi-clipboard-check', description: 'Заявки, согласования, комментарии' },
            { code: 'calendar', name: 'Календарь', icon: 'bi-calendar-event', description: 'События, напоминания, изменения' },
            { code: 'department', name: 'Отдел', icon: 'bi-people', description: 'Изменения в структуре отдела' },
            { code: 'profile', name: 'Профиль', icon: 'bi-person', description: 'Изменения профиля и безопасности' },
            { code: 'feed', name: 'Новости', icon: 'bi-newspaper', description: 'Публикации, комментарии, реакции' },
            { code: 'system', name: 'Система', icon: 'bi-gear', description: 'Системные уведомления и обновления' }
        ];
        
        let html = '<div class="row g-4">';
        
        categories.forEach(cat => {
            const setting = this.settings[cat.code] || {
                is_enabled: true,
                web_enabled: true,
                email_enabled: false,
                telegram_enabled: false
            };
            
            html += `
                <div class="col-md-6">
                    <div class="card h-100">
                        <div class="card-body">
                            <div class="d-flex align-items-start mb-3">
                                <div class="flex-shrink-0">
                                    <div class="settings-icon">
                                        <i class="${cat.icon}"></i>
                                    </div>
                                </div>
                                <div class="flex-grow-1 ms-3">
                                    <h5 class="card-title mb-1">${cat.name}</h5>
                                    <p class="text-muted small mb-3">${cat.description}</p>
                                    
                                    <div class="form-check form-switch mb-2">
                                        <input class="form-check-input setting-toggle" 
                                               type="checkbox" 
                                               id="enable_${cat.code}"
                                               data-category="${cat.code}"
                                               data-field="is_enabled"
                                               ${setting.is_enabled ? 'checked' : ''}>
                                        <label class="form-check-label" for="enable_${cat.code}">
                                            <strong>Включить уведомления</strong>
                                        </label>
                                    </div>
                                    
                                    <div class="ps-4 ${setting.is_enabled ? '' : 'd-none'}" id="channels_${cat.code}">
                                        <div class="form-check mb-2">
                                            <input class="form-check-input channel-toggle" 
                                                   type="checkbox" 
                                                   id="web_${cat.code}"
                                                   data-category="${cat.code}"
                                                   data-field="web_enabled"
                                                   ${setting.web_enabled ? 'checked' : ''}>
                                            <label class="form-check-label" for="web_${cat.code}">
                                                <i class="bi-globe"></i> Веб-уведомления
                                            </label>
                                        </div>
                                        
                                        <div class="form-check mb-2">
                                            <input class="form-check-input channel-toggle" 
                                                   type="checkbox" 
                                                   id="email_${cat.code}"
                                                   data-category="${cat.code}"
                                                   data-field="email_enabled"
                                                   ${setting.email_enabled ? 'checked' : ''}
                                                   disabled>
                                            <label class="form-check-label text-muted" for="email_${cat.code}">
                                                <i class="bi-envelope"></i> Email (скоро)
                                            </label>
                                        </div>
                                        
                                        <div class="form-check mb-2">
                                            <input class="form-check-input channel-toggle" 
                                                   type="checkbox" 
                                                   id="telegram_${cat.code}"
                                                   data-category="${cat.code}"
                                                   data-field="telegram_enabled"
                                                   ${setting.telegram_enabled ? 'checked' : ''}
                                                   disabled>
                                            <label class="form-check-label text-muted" for="telegram_${cat.code}">
                                                <i class="bi-telegram"></i> Telegram (скоро)
                                            </label>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            `;
        });
        
        html += '</div>';
        container.innerHTML = html;
        
        // Добавить обработчики
        this.attachEventHandlers();
    }
    
    attachEventHandlers() {
        // Обработчики для главных переключателей
        document.querySelectorAll('.setting-toggle').forEach(toggle => {
            toggle.addEventListener('change', async (e) => {
                const category = toggle.dataset.category;
                const field = toggle.dataset.field;
                const value = toggle.checked;
                
                // Показать/скрыть каналы
                const channels = document.getElementById(`channels_${category}`);
                if (channels) {
                    if (value) {
                        channels.classList.remove('d-none');
                    } else {
                        channels.classList.add('d-none');
                    }
                }
                
                await this.updateSetting(category, field, value);
            });
        });
        
        // Обработчики для каналов
        document.querySelectorAll('.channel-toggle').forEach(toggle => {
            toggle.addEventListener('change', async (e) => {
                const category = toggle.dataset.category;
                const field = toggle.dataset.field;
                const value = toggle.checked;
                
                await this.updateSetting(category, field, value);
            });
        });
    }
    
    async updateSetting(category, field, value) {
        try {
            const response = await fetch('/api/notifications/settings/category/update/', {
                method: 'PUT',
                credentials: 'same-origin',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.getCsrfToken()
                },
                body: JSON.stringify({
                    category: category,
                    [field]: value
                })
            });
            
            if (!response.ok) {
                throw new Error('Failed to update setting');
            }
            
            // Обновить локальные настройки
            if (!this.settings[category]) {
                this.settings[category] = {};
            }
            this.settings[category][field] = value;
            
            // Показать уведомление об успехе
            this.showToast('Настройки сохранены', 'success');
        } catch (error) {
            console.error('[Settings] Error updating:', error);
            this.showToast('Ошибка сохранения настроек', 'danger');
        }
    }
    
    setupSoundToggle() {
        const soundToggle = document.getElementById('soundToggle');
        if (soundToggle && window.notificationManager) {
            soundToggle.checked = window.notificationManager.soundEnabled;
            
            soundToggle.addEventListener('change', (e) => {
                window.notificationManager.saveSoundPreference(e.target.checked);
                this.showToast(
                    e.target.checked ? 'Звук включен' : 'Звук выключен',
                    'info'
                );
            });
        }
    }
    
    getCsrfToken() {
        return document.querySelector('[name=csrfmiddlewaretoken]')?.value || '';
    }
    
    showToast(message, type = 'info') {
        // Создать toast уведомление
        const toastContainer = document.getElementById('toastContainer') || this.createToastContainer();
        
        const toast = document.createElement('div');
        toast.className = `toast align-items-center text-white bg-${type} border-0`;
        toast.setAttribute('role', 'alert');
        toast.innerHTML = `
            <div class="d-flex">
                <div class="toast-body">${message}</div>
                <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
            </div>
        `;
        
        toastContainer.appendChild(toast);
        
        const bsToast = new bootstrap.Toast(toast, { delay: 3000 });
        bsToast.show();
        
        toast.addEventListener('hidden.bs.toast', () => {
            toast.remove();
        });
    }
    
    createToastContainer() {
        const container = document.createElement('div');
        container.id = 'toastContainer';
        container.className = 'toast-container position-fixed bottom-0 end-0 p-3';
        document.body.appendChild(container);
        return container;
    }
}

// Инициализация
document.addEventListener('DOMContentLoaded', () => {
    if (document.getElementById('settingsContainer')) {
        window.notificationSettingsManager = new NotificationSettingsManager();
    }
});
