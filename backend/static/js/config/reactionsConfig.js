/**
 * Reactions Config - загрузка доступных реакций из БД
 */

class ReactionsConfig {
    constructor() {
        this.reactions = [];
        this.loaded = false;
        this.loading = false;
        this.loadPromise = null;
        
        // Дефолтные реакции на случай ошибки загрузки
        this.defaultReactions = [
            { emoji: '👍', name: 'Лайк' },
            { emoji: '❤️', name: 'Сердце' },
            { emoji: '😂', name: 'Смех' },
            { emoji: '😮', name: 'Удивление' },
            { emoji: '😢', name: 'Грусть' },
            { emoji: '🙏', name: 'Спасибо' },
            { emoji: '👏', name: 'Аплодисменты' },
            { emoji: '🔥', name: 'Огонь' }
        ];
    }

    /**
     * Загружает доступные реакции из API
     * @returns {Promise<Array>} Массив объектов реакций
     */
    async load() {
        // Если уже загружается - возвращаем существующий промис
        if (this.loading) {
            return this.loadPromise;
        }

        // Если уже загружено - возвращаем кэш
        if (this.loaded) {
            return Promise.resolve(this.reactions);
        }

        this.loading = true;
        
        this.loadPromise = fetch('/api/v1/communications/reactions/available/')
            .then(response => {
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                return response.json();
            })
            .then(data => {
                if (data.ok && Array.isArray(data.reactions)) {
                    this.reactions = data.reactions;
                    this.loaded = true;
                    console.log('[ReactionsConfig] ✓ Loaded reactions from API:', this.reactions);
                    return this.reactions;
                } else {
                    throw new Error('Invalid API response format');
                }
            })
            .catch(error => {
                console.error('[ReactionsConfig] ✗ Failed to load reactions:', error);
                console.warn('[ReactionsConfig] Using default reactions as fallback');
                this.reactions = this.defaultReactions;
                this.loaded = true;
                return this.reactions;
            })
            .finally(() => {
                this.loading = false;
            });

        return this.loadPromise;
    }

    /**
     * Получает массив эмодзи для использования в UI
     * @returns {Array<string>} Массив эмодзи
     */
    getEmojis() {
        return this.reactions.map(r => r.emoji);
    }

    /**
     * Получает название реакции по эмодзи
     * @param {string} emoji 
     * @returns {string|null}
     */
    getName(emoji) {
        const reaction = this.reactions.find(r => r.emoji === emoji);
        return reaction ? reaction.name : null;
    }

    /**
     * Проверяет, доступна ли данная реакция
     * @param {string} emoji 
     * @returns {boolean}
     */
    isAvailable(emoji) {
        return this.reactions.some(r => r.emoji === emoji);
    }
}

// Создаём глобальный синглтон
const reactionsConfig = new ReactionsConfig();

export default reactionsConfig;
