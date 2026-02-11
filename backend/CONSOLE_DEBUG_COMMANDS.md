# 🔍 Команды для отладки календаря через консоль браузера

Откройте консоль браузера (F12 → Console) и выполните эти команды:

## 1️⃣ Проверить наличие интеграции

```javascript
// Должно вернуть объект, а не undefined
window.calendarIntegration
```

**Ожидаемый результат:**
```javascript
{
  fetchEventsForVisibleCalendars: ƒ,
  getVisibleCalendarIds: ƒ,
  getCalendars: ƒ,
  setVisibleCalendars: ƒ,
  refresh: ƒ,
  instances: {manager: {...}, modal: {...}, widget: {...}}
}
```

**Если undefined** → интеграция не инициализировалась!

---

## 2️⃣ Проверить виджет календаря

```javascript
window.calendarWidget
```

**Должен вернуть объект FullCalendar**

---

## 3️⃣ Проверить список календарей

```javascript
// Если интеграция работает:
window.calendarIntegration.getCalendars()

// Должно вернуть массив календарей:
// [{id: 1, title: "Personal", color: "#0d6efd", ...}, ...]
```

---

## 4️⃣ Проверить видимые календари

```javascript
window.calendarIntegration.getVisibleCalendarIds()

// Должно вернуть массив ID: [1, 2, 3]
```

---

## 5️⃣ Вручную загрузить события

```javascript
// Попробовать загрузить события для видимых календарей
const start = new Date('2026-02-01');
const end = new Date('2026-02-28');

window.calendarIntegration.fetchEventsForVisibleCalendars(start, end)
  .then(events => {
    console.log('✅ Events loaded:', events.length);
    console.table(events);
  })
  .catch(err => {
    console.error('❌ Error:', err);
  });
```

---

## 6️⃣ Проверить, загружен ли скрипт интеграции

```javascript
// Проверить, есть ли в DOM скрипт
document.querySelector('script[src*="calendarWidgetIntegration"]')

// Должен вернуть <script> элемент, если файл подключен
```

---

## 7️⃣ Вручную инициализировать интеграцию

Если интеграция не загрузилась автоматически, попробуйте вручную:

```javascript
// 1. Импортировать модуль (если ES6 modules работают)
import('/static/js/components/calendarWidgetIntegration.js')
  .then(module => {
    const { integrateCalendarManager } = module;
    const integration = integrateCalendarManager(window.calendarWidget);
    window.calendarIntegration = integration;
    console.log('✅ Integration manually initialized');
  })
  .catch(err => console.error('❌ Import failed:', err));
```

---

## 8️⃣ Перезагрузить события календаря

```javascript
// После того как интеграция инициализирована
if (window.calendarWidget && window.calendarWidget.refetchEvents) {
  window.calendarWidget.refetchEvents();
  console.log('🔄 Events refetched');
}
```

---

## 9️⃣ Проверить контейнер списка календарей

```javascript
// Проверить, существует ли контейнер
const container = document.getElementById('calendarListContainer');
console.log('Container exists:', !!container);
console.log('Container HTML:', container?.innerHTML.substring(0, 200));
```

---

## 🔟 Проверить модальное окно

```javascript
// Проверить, есть ли модальное окно
const modal = document.getElementById('calendarManageModal');
console.log('Modal exists:', !!modal);

// Попробовать открыть модальное окно
if (window.calendarIntegration?.instances?.modal) {
  window.calendarIntegration.instances.modal.openForCreate();
}
```

---

## 🐛 Диагностика проблемы

Выполните все команды по порядку и скопируйте результаты. Это поможет понять, на каком этапе происходит сбой:

```javascript
console.log('=== Calendar Integration Debug ===');
console.log('1. calendarIntegration:', typeof window.calendarIntegration);
console.log('2. calendarWidget:', typeof window.calendarWidget);
console.log('3. Container:', !!document.getElementById('calendarListContainer'));
console.log('4. Modal:', !!document.getElementById('calendarManageModal'));
console.log('5. Create button:', !!document.querySelector('[data-action="create-calendar"]'));
console.log('=================================');
```

---

## 🔧 Если интеграция undefined

Проверьте, загружается ли файл `calendar_scripts.html`:

```javascript
// Найти все script теги с calendar
Array.from(document.querySelectorAll('script[type="module"]'))
  .filter(s => s.textContent.includes('calendar'))
  .forEach(s => console.log('Found:', s.textContent.substring(0, 100)));
```

---

## 📊 Полный отчёт о состоянии

Скопируйте и выполните весь блок:

```javascript
(function debugCalendar() {
  const report = {
    integration: typeof window.calendarIntegration,
    widget: typeof window.calendarWidget,
    container: !!document.getElementById('calendarListContainer'),
    modal: !!document.getElementById('calendarManageModal'),
    createButton: !!document.querySelector('[data-action="create-calendar"]'),
    scripts: Array.from(document.querySelectorAll('script[type="module"]')).length,
    errors: []
  };
  
  if (window.calendarIntegration) {
    try {
      report.calendars = window.calendarIntegration.getCalendars().length;
      report.visibleIds = window.calendarIntegration.getVisibleCalendarIds();
    } catch (e) {
      report.errors.push('Error accessing integration: ' + e.message);
    }
  }
  
  console.table(report);
  return report;
})();
```

---

Выполните команды и покажите результаты! 🔍
