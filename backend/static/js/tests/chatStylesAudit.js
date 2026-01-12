/**
 * Аудит CSS стилей на странице чата
 * Проверяет какие стили используются, а какие нет
 * 
 * Запуск из консоли браузера:
 * 
 * 1. Загрузить скрипт:
 *    const script = document.createElement('script');
 *    script.src = '/static/js/tests/chatStylesAudit.js';
 *    script.type = 'module';
 *    document.head.appendChild(script);
 * 
 * 2. Запустить аудит:
 *    window.ChatStylesAudit.runFullAudit()
 *    window.ChatStylesAudit.checkChatDetailStyles()
 *    window.ChatStylesAudit.checkMessageStyles()
 *    window.ChatStylesAudit.findUnusedStyles()
 */

class ChatStylesAudit {
    constructor() {
        this.results = {
            total: 0,
            used: 0,
            unused: 0,
            details: []
        };
        
        // CSS файлы для проверки
        this.cssFiles = [
            '/static/css/components/chat-detail.css',
            '/static/css/message-reactions.css',
            '/static/css/message-context-menu.css',
            '/static/css/message-selection.css',
            '/static/css/components/chat-polls.css'
        ];
    }

    /**
     * Получает все CSS правила из stylesheet
     */
    getCSSRules(stylesheet) {
        try {
            return Array.from(stylesheet.cssRules || stylesheet.rules || []);
        } catch (e) {
            console.warn('Не удалось получить правила из stylesheet:', e);
            return [];
        }
    }

    /**
     * Извлекает селекторы из CSS правила
     */
    extractSelectors(rule) {
        const selectors = [];
        
        if (rule.selectorText) {
            // Разбиваем составные селекторы
            const parts = rule.selectorText.split(',').map(s => s.trim());
            selectors.push(...parts);
        }
        
        // Рекурсивно обрабатываем медиа-запросы
        if (rule.cssRules) {
            for (const subRule of this.getCSSRules(rule)) {
                selectors.push(...this.extractSelectors(subRule));
            }
        }
        
        return selectors;
    }

    /**
     * Проверяет используется ли селектор в DOM
     */
    isSelectorUsed(selector) {
        try {
            // Пропускаем псевдо-элементы и псевдо-классы для точной проверки
            const cleanSelector = selector
                .replace(/::(before|after|placeholder|selection)/g, '')
                .replace(/:(hover|focus|active|visited|link|first-child|last-child|nth-child\([^)]+\)|not\([^)]+\))/g, '')
                .trim();
            
            if (!cleanSelector || cleanSelector === '') {
                return { used: false, reason: 'empty_after_cleanup' };
            }
            
            const elements = document.querySelectorAll(cleanSelector);
            return {
                used: elements.length > 0,
                count: elements.length,
                selector: cleanSelector
            };
        } catch (e) {
            return { used: false, reason: 'invalid_selector', error: e.message };
        }
    }

    /**
     * Сканирует все стили связанные с чатом
     */
    async scanChatStyles() {
        console.log('🔍 Сканирование CSS стилей чата...\n');
        
        const allSelectors = new Map(); // selector -> { used, files, count }
        
        // Проходим по всем загруженным stylesheets
        for (const stylesheet of document.styleSheets) {
            try {
                const href = stylesheet.href || 'inline';
                
                // Проверяем только файлы связанные с чатом
                const isChatRelated = this.cssFiles.some(file => href.includes(file)) ||
                                     href.includes('chat') ||
                                     href.includes('message');
                
                if (!isChatRelated && stylesheet.href) continue;
                
                const rules = this.getCSSRules(stylesheet);
                
                for (const rule of rules) {
                    const selectors = this.extractSelectors(rule);
                    
                    for (const selector of selectors) {
                        if (!allSelectors.has(selector)) {
                            const usage = this.isSelectorUsed(selector);
                            allSelectors.set(selector, {
                                original: selector,
                                used: usage.used,
                                count: usage.count || 0,
                                files: [href],
                                reason: usage.reason
                            });
                        } else {
                            const existing = allSelectors.get(selector);
                            if (!existing.files.includes(href)) {
                                existing.files.push(href);
                            }
                        }
                    }
                }
            } catch (e) {
                console.warn('Ошибка при обработке stylesheet:', e);
            }
        }
        
        return allSelectors;
    }

    /**
     * Проверяет конкретный CSS файл
     */
    async checkSpecificFile(filePath) {
        console.log(`📄 Проверка файла: ${filePath}\n`);
        
        const results = {
            file: filePath,
            total: 0,
            used: 0,
            unused: 0,
            selectors: []
        };
        
        for (const stylesheet of document.styleSheets) {
            if (stylesheet.href && stylesheet.href.includes(filePath)) {
                const rules = this.getCSSRules(stylesheet);
                
                for (const rule of rules) {
                    const selectors = this.extractSelectors(rule);
                    
                    for (const selector of selectors) {
                        const usage = this.isSelectorUsed(selector);
                        results.total++;
                        
                        if (usage.used) {
                            results.used++;
                        } else {
                            results.unused++;
                        }
                        
                        results.selectors.push({
                            selector,
                            used: usage.used,
                            count: usage.count || 0,
                            reason: usage.reason
                        });
                    }
                }
            }
        }
        
        return results;
    }

    /**
     * Полный аудит всех стилей
     */
    async runFullAudit() {
        console.log('\n' + '='.repeat(80));
        console.log('🎨 ПОЛНЫЙ АУДИТ CSS СТИЛЕЙ ЧАТА');
        console.log('='.repeat(80) + '\n');
        
        const allSelectors = await this.scanChatStyles();
        
        const used = [];
        const unused = [];
        
        for (const [selector, data] of allSelectors) {
            if (data.used) {
                used.push({ selector, ...data });
            } else {
                unused.push({ selector, ...data });
            }
        }
        
        // Сортируем по количеству использований
        used.sort((a, b) => b.count - a.count);
        unused.sort((a, b) => a.selector.localeCompare(b.selector));
        
        console.log('📊 СТАТИСТИКА:');
        console.log('─'.repeat(80));
        console.log(`Всего селекторов: ${allSelectors.size}`);
        console.log(`✅ Используется: ${used.length} (${(used.length / allSelectors.size * 100).toFixed(1)}%)`);
        console.log(`❌ Не используется: ${unused.length} (${(unused.length / allSelectors.size * 100).toFixed(1)}%)`);
        console.log('─'.repeat(80) + '\n');
        
        // ТОП-10 самых используемых стилей
        console.log('🏆 ТОП-10 САМЫХ ИСПОЛЬЗУЕМЫХ СТИЛЕЙ:');
        console.log('─'.repeat(80));
        used.slice(0, 10).forEach((item, i) => {
            console.log(`${i + 1}. ${item.selector}`);
            console.log(`   📍 Использований: ${item.count}`);
            console.log(`   📁 Файлы: ${item.files.join(', ')}\n`);
        });
        
        // Неиспользуемые стили
        if (unused.length > 0) {
            console.log('\n❌ НЕИСПОЛЬЗУЕМЫЕ СТИЛИ:');
            console.log('─'.repeat(80));
            
            // Группируем по файлам
            const byFile = {};
            unused.forEach(item => {
                item.files.forEach(file => {
                    if (!byFile[file]) byFile[file] = [];
                    byFile[file].push(item.selector);
                });
            });
            
            for (const [file, selectors] of Object.entries(byFile)) {
                const fileName = file.split('/').pop();
                console.log(`\n📄 ${fileName} (${selectors.length} неиспользуемых):`);
                selectors.slice(0, 20).forEach(sel => {
                    console.log(`   • ${sel}`);
                });
                if (selectors.length > 20) {
                    console.log(`   ... и ещё ${selectors.length - 20}`);
                }
            }
        }
        
        console.log('\n' + '='.repeat(80));
        console.log('✅ АУДИТ ЗАВЕРШЁН');
        console.log('='.repeat(80) + '\n');
        
        // Сохраняем результаты
        this.lastAudit = {
            timestamp: new Date().toISOString(),
            total: allSelectors.size,
            used: used.length,
            unused: unused.length,
            usedSelectors: used,
            unusedSelectors: unused
        };
        
        return this.lastAudit;
    }

    /**
     * Проверяет стили chat-detail.css
     */
    async checkChatDetailStyles() {
        console.log('\n📋 АУДИТ: chat-detail.css\n');
        const result = await this.checkSpecificFile('chat-detail.css');
        this.printFileResults(result);
        return result;
    }

    /**
     * Проверяет стили сообщений
     */
    async checkMessageStyles() {
        console.log('\n📋 АУДИТ: Стили сообщений\n');
        
        const files = [
            'message-reactions.css',
            'message-context-menu.css',
            'message-selection.css'
        ];
        
        const results = [];
        for (const file of files) {
            const result = await this.checkSpecificFile(file);
            results.push(result);
        }
        
        // Общая статистика
        const total = results.reduce((sum, r) => sum + r.total, 0);
        const used = results.reduce((sum, r) => sum + r.used, 0);
        const unused = results.reduce((sum, r) => sum + r.unused, 0);
        
        console.log('\n' + '='.repeat(60));
        console.log('📊 ОБЩАЯ СТАТИСТИКА ПО СТИЛЯМ СООБЩЕНИЙ:');
        console.log('='.repeat(60));
        console.log(`Всего: ${total}`);
        console.log(`✅ Используется: ${used} (${(used / total * 100).toFixed(1)}%)`);
        console.log(`❌ Не используется: ${unused} (${(unused / total * 100).toFixed(1)}%)`);
        console.log('='.repeat(60) + '\n');
        
        return results;
    }

    /**
     * Находит дубликаты стилей
     */
    findDuplicateStyles() {
        console.log('\n🔎 ПОИСК ДУБЛИРУЮЩИХСЯ СТИЛЕЙ...\n');
        
        const styleMap = new Map(); // CSS text -> selectors[]
        
        for (const stylesheet of document.styleSheets) {
            try {
                const rules = this.getCSSRules(stylesheet);
                
                for (const rule of rules) {
                    if (rule.style && rule.selectorText) {
                        const cssText = rule.style.cssText;
                        if (!styleMap.has(cssText)) {
                            styleMap.set(cssText, []);
                        }
                        styleMap.get(cssText).push(rule.selectorText);
                    }
                }
            } catch (e) {
                // Skip
            }
        }
        
        const duplicates = [];
        for (const [cssText, selectors] of styleMap) {
            if (selectors.length > 1) {
                duplicates.push({ cssText, selectors, count: selectors.length });
            }
        }
        
        duplicates.sort((a, b) => b.count - a.count);
        
        console.log(`Найдено ${duplicates.length} групп дублирующихся стилей:\n`);
        
        duplicates.slice(0, 10).forEach((dup, i) => {
            console.log(`${i + 1}. ${dup.count} дубликатов:`);
            console.log(`   Стили: ${dup.cssText.substring(0, 100)}${dup.cssText.length > 100 ? '...' : ''}`);
            console.log(`   Селекторы:`);
            dup.selectors.forEach(sel => console.log(`     • ${sel}`));
            console.log('');
        });
        
        return duplicates;
    }

    /**
     * Выводит результаты для файла
     */
    printFileResults(result) {
        console.log('─'.repeat(60));
        console.log(`📄 Файл: ${result.file}`);
        console.log('─'.repeat(60));
        console.log(`Всего селекторов: ${result.total}`);
        console.log(`✅ Используется: ${result.used} (${(result.used / result.total * 100).toFixed(1)}%)`);
        console.log(`❌ Не используется: ${result.unused} (${(result.unused / result.total * 100).toFixed(1)}%)`);
        console.log('─'.repeat(60));
        
        if (result.unused > 0) {
            const unusedList = result.selectors.filter(s => !s.used);
            console.log(`\n❌ Неиспользуемые селекторы (${unusedList.length}):`);
            unusedList.slice(0, 20).forEach(s => {
                console.log(`   • ${s.selector}`);
            });
            if (unusedList.length > 20) {
                console.log(`   ... и ещё ${unusedList.length - 20}`);
            }
        }
        
        console.log('\n');
    }

    /**
     * Анализирует специфичность селекторов
     */
    analyzeSpecificity() {
        console.log('\n⚖️ АНАЛИЗ СПЕЦИФИЧНОСТИ СЕЛЕКТОРОВ...\n');
        
        const specificityMap = new Map();
        
        for (const stylesheet of document.styleSheets) {
            try {
                const rules = this.getCSSRules(stylesheet);
                
                for (const rule of rules) {
                    if (rule.selectorText) {
                        const selectors = rule.selectorText.split(',').map(s => s.trim());
                        
                        for (const selector of selectors) {
                            const spec = this.calculateSpecificity(selector);
                            const key = spec.join('-');
                            
                            if (!specificityMap.has(key)) {
                                specificityMap.set(key, []);
                            }
                            specificityMap.get(key).push(selector);
                        }
                    }
                }
            } catch (e) {
                // Skip
            }
        }
        
        const entries = Array.from(specificityMap.entries())
            .map(([key, selectors]) => ({
                specificity: key,
                count: selectors.length,
                examples: selectors.slice(0, 3)
            }))
            .sort((a, b) => b.count - a.count);
        
        console.log('📊 Распределение по специфичности:\n');
        entries.slice(0, 15).forEach((entry, i) => {
            console.log(`${i + 1}. [${entry.specificity}] - ${entry.count} селекторов`);
            entry.examples.forEach(ex => console.log(`     ${ex}`));
            console.log('');
        });
        
        return entries;
    }

    /**
     * Вычисляет специфичность селектора
     */
    calculateSpecificity(selector) {
        let ids = 0;
        let classes = 0;
        let elements = 0;
        
        // Подсчет ID
        ids = (selector.match(/#/g) || []).length;
        
        // Подсчет классов, атрибутов, псевдоклассов
        classes = (selector.match(/\./g) || []).length;
        classes += (selector.match(/\[/g) || []).length;
        classes += (selector.match(/:/g) || []).length;
        
        // Подсчет элементов и псевдоэлементов
        elements = (selector.match(/\b[a-z]+\b/g) || []).length;
        elements += (selector.match(/::/g) || []).length;
        
        return [ids, classes, elements];
    }

    /**
     * Экспортирует результаты в JSON
     */
    exportResults() {
        if (!this.lastAudit) {
            console.error('❌ Сначала запустите runFullAudit()');
            return;
        }
        
        const json = JSON.stringify(this.lastAudit, null, 2);
        const blob = new Blob([json], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        
        const a = document.createElement('a');
        a.href = url;
        a.download = `chat-styles-audit-${Date.now()}.json`;
        a.click();
        
        console.log('✅ Результаты экспортированы в JSON');
    }
}

// Экспортируем в глобальную область
window.ChatStylesAudit = new ChatStylesAudit();

export default ChatStylesAudit;
