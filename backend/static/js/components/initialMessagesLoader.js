/**
 * Initial Messages Loader
 * Загружает начальные сообщения чата при открытии страницы
 */

export class InitialMessagesLoader {
    constructor(config = {}) {
        this.chatId = config.chatId;
        this.fetchUrl = config.fetchUrl;
        this.limit = config.limit || 30;
        this.messageRenderer = config.messageRenderer;
        this.onLoaded = config.onLoaded || (() => {});
        this.onError = config.onError || (() => {});
    }

    /**
     * Загружает начальные сообщения
     */
    async load() {
        console.log('[InitialMessagesLoader] Loading initial messages for chat:', this.chatId);

        try {
            const url = `${this.fetchUrl}?limit=${this.limit}`;
            const response = await fetch(url, {
                method: 'GET',
                headers: {
                    'Accept': 'application/json'
                }
            });

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }

            const data = await response.json();
            
            if (!data.ok) {
                throw new Error(data.error || 'Ошибка загрузки');
            }

            console.log('[InitialMessagesLoader] Loaded', data.messages.length, 'messages');

            // Рендерим сообщения
            if (this.messageRenderer && data.messages.length > 0) {
                this.messageRenderer.renderMessages(data.messages);
            }
            
            // Убираем индикатор загрузки
            const loader = document.getElementById('initialLoader');
            if (loader) {
                loader.remove();
            }

            // Callback
            this.onLoaded({
                messages: data.messages,
                hasMore: data.has_more,
                nextBeforeId: data.next_before_id,
                nextBeforeTs: data.next_before_ts
            });

            return data;

        } catch (error) {
            console.error('[InitialMessagesLoader] Load failed:', error);
            this.onError(error);
            throw error;
        }
    }
}

/**
 * Фабричная функция
 */
export function createInitialMessagesLoader(config) {
    return new InitialMessagesLoader(config);
}
