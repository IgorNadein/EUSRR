# 🔧 Исправление проблемы инициализации calendar integration

## Проблема
`window.calendarIntegration` = undefined, но скрипт подключён.

## Быстрое решение - выполните в консоли:

```javascript
// Проверка наличия скрипта
const scripts = Array.from(document.querySelectorAll('script[type="module"]'));
console.log('Module scripts found:', scripts.length);
scripts.forEach((s, i) => {
  if (s.textContent.includes('calendar')) {
    console.log(`Script ${i}:`, s.textContent.substring(0, 200));
  }
});
```

## Если скрипт найден, но не работает - вручную загрузите:

```javascript
(async function manualInit() {
  try {
    console.log('🔄 Manually loading calendar integration...');
    
    // Импорт модуля
    const module = await import('/static/js/components/calendarWidgetIntegration.js');
    console.log('✅ Module loaded:', module);
    
    // Инициализация
    const { integrateCalendarManager } = module;
    const integration = integrateCalendarManager(window.calendarWidget);
    
    if (integration) {
      window.calendarIntegration = integration;
      console.log('✅ Integration initialized successfully!');
      console.log('Calendars:', integration.getCalendars().length);
      console.log('Visible:', integration.getVisibleCalendarIds());
      
      // Перезагрузить события
      if (window.calendarWidget.refetchEvents) {
        window.calendarWidget.refetchEvents();
        console.log('🔄 Events refetched with new integration');
      }
    }
  } catch (error) {
    console.error('❌ Manual init failed:', error);
  }
})();
```

## После выполнения проверьте:

```javascript
// Должно вернуть объект, а не undefined
window.calendarIntegration

// Должно показать логи с новой системой
window.calendarWidget.refetchEvents()
```
