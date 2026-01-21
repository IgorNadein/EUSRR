/**
 * Reactions Config - загрузка доступных реакций из БД
 */

class ReactionsConfig {
    constructor() {
        this.reactions = [];
        this.loaded = false;
        
        // Дефолтные реакции
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
     * Загружает доступные реакции (использует дефолтные)
     * @returns {Promise<Array>} Массив объектов реакций
     */
    async load() {
        // Если уже загружено - возвращаем кэш
        if (this.loaded) {
            return Promise.resolve(this.reactions);
        }

        // Используем дефолтные реакции (API эндпоинт не реализован)
        this.reactions = this.defaultReactions;
        this.loaded = true;
        console.log('[ReactionsConfig] ✓ Using default reactions:', this.reactions.length);
        
        return Promise.resolve(this.reactions);
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
