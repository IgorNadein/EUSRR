/**
 * DateGroupManager - Менеджер группировки сообщений по датам
 * 
 * Основано на архитектуре Telegram Web:
 * - Группирует сообщения в date-группы
 * - Управляет DOM структурой message-date-group
 * - Поддерживает sticky positioning
 * 
 * Структура DOM:
 * <div class="message-date-group" data-date="Сегодня">
 *   <div class="sticky-date interactive"><span dir="auto">Сегодня</span></div>
 *   <div class="messages-container">
 *     <!-- Сообщения здесь -->
 *   </div>
 * </div>
 * 
 * @module managers/dateGroupManager
 */

import { DateDividerManager } from '../utils/dateDividers.js';

/**
 * Менеджер для группировки сообщений по датам
 */
export class DateGroupManager {
    /**
     * @param {Object} options - Опции конфигурации
     * @param {HTMLElement} options.container - Контейнер для групп
     * @param {boolean} [options.enableSticky=true] - Включить sticky positioning
     * @param {boolean} [options.interactive=false] - Сделать даты кликабельными
     */
    constructor(options = {}) {
        this.container = options.container;
        this.enableSticky = options.enableSticky !== false;
        this.interactive = options.interactive || false;
        
        // Map для быстрого доступа к группам по дате
        // ключ: текст даты ("Сегодня", "Вчера" и т.д.)
        // значение: HTMLElement группы
        this.dateGroups = new Map();
        
        console.log('[DateGroupManager] Initialized', {
            enableSticky: this.enableSticky,
            interactive: this.interactive
        });
    }

    /**
     * Создает новую date группу
     * 
     * @param {string} dateText - Текст даты ("Сегодня", "Вчера", "5 января 2026")
     * @param {number} [timestamp] - Unix timestamp для data-атрибута
     * @returns {HTMLElement} DOM элемент группы
     * 
     * @example
     * const group = manager.createDateGroup('Сегодня', Date.now());
     * container.appendChild(group);
     */
    createDateGroup(dateText, timestamp) {
        // Основной контейнер группы
        const groupEl = document.createElement('div');
        groupEl.className = 'message-date-group';
        groupEl.setAttribute('data-date', dateText);
        
        if (timestamp) {
            groupEl.setAttribute('data-timestamp', timestamp);
        }

        // Sticky date header
        const stickyDate = DateDividerManager.createStickyDate(dateText, this.interactive);
        
        // Контейнер для сообщений внутри группы
        const messagesContainer = document.createElement('div');
        messagesContainer.className = 'messages-container';

        // Собираем структуру
        groupEl.appendChild(stickyDate);
        groupEl.appendChild(messagesContainer);

        // Сохраняем в Map
        this.dateGroups.set(dateText, groupEl);

        console.log('[DateGroupManager] Created date group:', dateText);
        
        return groupEl;
    }

    /**
     * Получает существующую группу или создает новую
     * 
     * @param {string} dateText - Текст даты
     * @param {number} [timestamp] - Unix timestamp
     * @returns {HTMLElement} DOM элемент группы
     * 
     * @example
     * const group = manager.getOrCreateGroup('Сегодня');
     * group.querySelector('.messages-container').appendChild(messageEl);
     */
    getOrCreateGroup(dateText, timestamp) {
        let group = this.dateGroups.get(dateText);
        
        if (!group) {
            group = this.createDateGroup(dateText, timestamp);
            // Добавляем в контейнер
            if (this.container) {
                this.container.appendChild(group);
            }
        }
        
        return group;
    }

    /**
     * Находит группу по тексту даты
     * 
     * @param {string} dateText - Текст даты
     * @returns {HTMLElement|null} DOM элемент группы или null
     */
    findGroup(dateText) {
        return this.dateGroups.get(dateText) || null;
    }

    /**
     * Добавляет сообщение в соответствующую date группу
     * 
     * @param {HTMLElement} messageEl - DOM элемент сообщения
     * @param {string} dateText - Текст даты
     * @param {number} [timestamp] - Unix timestamp сообщения
     * @param {string} [position='append'] - Позиция: 'append' или 'prepend'
     * 
     * @example
     * manager.addMessageToGroup(messageEl, 'Сегодня', Date.now());
     */
    addMessageToGroup(messageEl, dateText, timestamp, position = 'append') {
        const group = this.getOrCreateGroup(dateText, timestamp);
        const messagesContainer = group.querySelector('.messages-container');
        
        if (position === 'prepend') {
            messagesContainer.insertBefore(messageEl, messagesContainer.firstChild);
        } else {
            messagesContainer.appendChild(messageEl);
        }
    }

    /**
     * Группирует массив сообщений и создает date groups
     * Основной метод для массового рендеринга
     * 
     * @param {Array} messages - Массив сообщений (уже отсортированных)
     * @param {Function} renderMessageFn - Функция рендеринга сообщения (msg) => HTMLElement
     * @param {string} [position='append'] - Позиция добавления: 'append' или 'prepend'
     * @returns {Array<HTMLElement>} Массив созданных date groups
     * 
     * @example
     * const groups = manager.groupAndRender(messages, (msg) => {
     *     const el = document.createElement('div');
     *     el.textContent = msg.content;
     *     return el;
     * });
     */
    groupAndRender(messages, renderMessageFn, position = 'append') {
        const createdGroups = [];
        let currentDateText = null;
        let currentGroup = null;

        // ✅ FIX: При prepend инвертируем массив для сохранения хронологического порядка
        // Без этого insertBefore в цикле перевернет сообщения задом наперед
        const messagesToProcess = position === 'prepend' ? [...messages].reverse() : messages;

        for (const message of messagesToProcess) {
            const messageDate = DateDividerManager.getMessageDate(message);
            const dateText = DateDividerManager.formatDay(messageDate);

            // Если дата изменилась - создаем новую группу
            if (dateText !== currentDateText) {
                currentGroup = this.getOrCreateGroup(dateText, messageDate.getTime());
                createdGroups.push(currentGroup);
                currentDateText = dateText;
            }

            // Рендерим сообщение и добавляем в группу
            const messageEl = renderMessageFn(message);
            const messagesContainer = currentGroup.querySelector('.messages-container');
            
            if (position === 'prepend') {
                messagesContainer.insertBefore(messageEl, messagesContainer.firstChild);
            } else {
                messagesContainer.appendChild(messageEl);
            }
        }

        console.log('[DateGroupManager] Grouped messages:', {
            totalMessages: messages.length,
            dateGroups: createdGroups.length
        });

        return createdGroups;
    }

    /**
     * Обновляет текст даты в группе (для live update после полуночи)
     * 
     * @param {string} oldDateText - Старый текст даты
     * @param {string} newDateText - Новый текст даты
     * 
     * @example
     * // После полуночи "Сегодня" становится "Вчера"
     * manager.updateGroupDate('Сегодня', 'Вчера');
     */
    updateGroupDate(oldDateText, newDateText) {
        const group = this.dateGroups.get(oldDateText);
        if (!group) return;

        // Обновляем атрибут
        group.setAttribute('data-date', newDateText);

        // Обновляем текст в sticky header
        const stickyDate = group.querySelector('.sticky-date span');
        if (stickyDate) {
            stickyDate.textContent = newDateText;
        }

        // Обновляем Map
        this.dateGroups.delete(oldDateText);
        this.dateGroups.set(newDateText, group);

        console.log('[DateGroupManager] Updated group date:', {
            from: oldDateText,
            to: newDateText
        });
    }

    /**
     * Удаляет группу по тексту даты
     * 
     * @param {string} dateText - Текст даты
     * @returns {boolean} true если группа была удалена
     */
    removeGroup(dateText) {
        const group = this.dateGroups.get(dateText);
        if (!group) return false;

        group.remove();
        this.dateGroups.delete(dateText);

        console.log('[DateGroupManager] Removed group:', dateText);
        return true;
    }

    /**
     * Удаляет пустые группы (без сообщений)
     * Полезно после удаления сообщений
     * 
     * @returns {number} Количество удаленных групп
     * 
     * @example
     * const removed = manager.removeEmptyGroups();
     * console.log(`Removed ${removed} empty groups`);
     */
    removeEmptyGroups() {
        let removedCount = 0;

        for (const [dateText, group] of this.dateGroups.entries()) {
            const messagesContainer = group.querySelector('.messages-container');
            
            if (!messagesContainer.hasChildNodes()) {
                group.remove();
                this.dateGroups.delete(dateText);
                removedCount++;
            }
        }

        if (removedCount > 0) {
            console.log('[DateGroupManager] Removed empty groups:', removedCount);
        }

        return removedCount;
    }

    /**
     * Очищает все группы
     * 
     * @example
     * manager.clear(); // Полная очистка перед перерисовкой
     */
    clear() {
        for (const group of this.dateGroups.values()) {
            group.remove();
        }
        
        this.dateGroups.clear();
        console.log('[DateGroupManager] Cleared all groups');
    }

    /**
     * Получает все date groups в порядке появления в DOM
     * 
     * @returns {Array<HTMLElement>} Массив групп
     */
    getAllGroups() {
        return Array.from(this.dateGroups.values());
    }

    /**
     * Получает количество групп
     * 
     * @returns {number}
     */
    getGroupCount() {
        return this.dateGroups.size;
    }

    /**
     * Получает контейнер сообщений для конкретной даты
     * 
     * @param {string} dateText - Текст даты
     * @returns {HTMLElement|null} Контейнер сообщений или null
     * 
     * @example
     * const container = manager.getMessagesContainer('Сегодня');
     * if (container) {
     *     console.log('Messages count:', container.children.length);
     * }
     */
    getMessagesContainer(dateText) {
        const group = this.findGroup(dateText);
        return group ? group.querySelector('.messages-container') : null;
    }

    /**
     * Вставляет группу в правильное место (по timestamp)
     * Используется при prepend сообщений (загрузка старых)
     * 
     * @param {HTMLElement} newGroup - Новая группа
     * @param {number} timestamp - Unix timestamp группы
     * 
     * @example
     * const oldGroup = manager.createDateGroup('5 января', oldTimestamp);
     * manager.insertGroupSorted(oldGroup, oldTimestamp);
     */
    insertGroupSorted(newGroup, timestamp) {
        if (!this.container) {
            console.warn('[DateGroupManager] No container set');
            return;
        }

        const existingGroups = this.container.querySelectorAll('.message-date-group');
        
        // Ищем правильное место для вставки
        let insertBefore = null;
        for (const group of existingGroups) {
            const groupTimestamp = parseInt(group.getAttribute('data-timestamp') || '0');
            if (timestamp < groupTimestamp) {
                insertBefore = group;
                break;
            }
        }

        if (insertBefore) {
            this.container.insertBefore(newGroup, insertBefore);
        } else {
            this.container.appendChild(newGroup);
        }
    }

    /**
     * Обновляет интерактивность дат (кликабельность)
     * 
     * @param {boolean} interactive - Включить/выключить интерактивность
     */
    setInteractive(interactive) {
        this.interactive = interactive;
        
        // Обновляем все существующие группы
        for (const group of this.dateGroups.values()) {
            const stickyDate = group.querySelector('.sticky-date');
            if (stickyDate) {
                if (interactive) {
                    stickyDate.classList.add('interactive');
                } else {
                    stickyDate.classList.remove('interactive');
                }
            }
        }

        console.log('[DateGroupManager] Interactive mode:', interactive);
    }

    /**
     * Получает статистику по группам
     * 
     * @returns {Object} Статистика
     */
    getStats() {
        const stats = {
            totalGroups: this.dateGroups.size,
            groups: []
        };

        for (const [dateText, group] of this.dateGroups.entries()) {
            const messagesContainer = group.querySelector('.messages-container');
            stats.groups.push({
                date: dateText,
                messageCount: messagesContainer.children.length,
                timestamp: group.getAttribute('data-timestamp')
            });
        }

        return stats;
    }
}

export default DateGroupManager;
