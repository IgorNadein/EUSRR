# Гайд по бэйджам в стиле Telegram

## Обзор

Применены лучшие практики Telegram Web K для создания идеальных бэйджей (счетчиков непрочитанных сообщений, уведомлений).

## Ключевые принципы Telegram

### 1. **Идеальные круги**
```css
border-radius: 10px; /* НЕ 50% - фиксированное значение */
```

### 2. **Правильные пропорции**
- Высота: `20px` (стандарт), `18px` (малый), `24px` (большой)
- Padding: `0 6px` для текста
- Font-size: `11px` (отлично читается)
- Font-weight: `600` (полужирный)

### 3. **Мягкие тени**
```css
box-shadow: 0 2px 4px rgba(0, 0, 0, 0.15);
```

### 4. **Плавные анимации**
- Появление: `scale(0) → scale(1)` с `cubic-bezier(0.175, 0.885, 0.32, 1.275)`
- Пульсация: `scale(1) → scale(1.15) → scale(1)`
- Transition: `0.2s` для быстрого отклика

## Использование

### Базовый бэйдж
```html
<span class="badge-telegram">5</span>
```

### С размерами
```html
<span class="badge-telegram badge-telegram-sm">1</span>
<span class="badge-telegram">5</span>
<span class="badge-telegram badge-telegram-lg">12</span>
```

### Цветовые варианты
```html
<span class="badge-telegram badge-telegram-primary">3</span>
<span class="badge-telegram badge-telegram-muted">2</span>
<span class="badge-telegram badge-telegram-mention">@</span>
```

### С позиционированием
```html
<!-- На аватаре -->
<div class="avatar">
  <img src="avatar.jpg" alt="Avatar">
  <span class="badge-telegram badge-telegram-avatar">5</span>
</div>

<!-- На кнопке -->
<button class="btn">
  <i class="bi bi-bell"></i>
  <span class="badge-telegram badge-telegram-button">3</span>
</button>
```

### С анимацией
```html
<span class="badge-telegram animate-in">5</span>
<span class="badge-telegram pulse">1</span>
```

### Точка (без числа)
```html
<span class="badge-telegram badge-telegram-dot"></span>
```

## Интеграция в проект

### 1. Подключить CSS
```html
<link rel="stylesheet" href="{% static 'css/components/badges-telegram-style.css' %}">
```

### 2. Обновить существующие бэйджи

**Было:**
```html
<span class="badge bg-danger">5</span>
```

**Стало:**
```html
<span class="badge-telegram">5</span>
```

### 3. JavaScript для динамических обновлений
```javascript
// Обновление счетчика с анимацией
function updateBadge(element, count) {
  if (count > 0) {
    element.textContent = count;
    element.classList.add('pulse');
    
    setTimeout(() => {
      element.classList.remove('pulse');
    }, 600);
  } else {
    element.textContent = '';
  }
}

// Пример
const badge = document.querySelector('.badge-telegram');
updateBadge(badge, 5);
```

## Преимущества перед старым подходом

| Старый подход | Telegram подход | Улучшение |
|---------------|-----------------|-----------|
| `border-radius: 50%` | `border-radius: 10px` | Идеальные круги при любом размере |
| `font-size: 0.65rem` | `font-size: 11px` | Лучшая читаемость |
| `padding: 2px 5px` | `padding: 0 6px` | Правильная центровка |
| Нет анимаций | `cubic-bezier` анимации | Плавность как в Telegram |
| `box-shadow: 0 1px 3px` | `box-shadow: 0 2px 4px` | Более выразительная тень |

## Примеры из Telegram Web K

### Непрочитанные сообщения
```html
<span class="badge-telegram">99+</span>
```

### Упоминания
```html
<span class="badge-telegram badge-telegram-mention">@</span>
```

### Приглашенные чаты
```html
<span class="badge-telegram badge-telegram-primary">3</span>
```

### Точка уведомления
```html
<span class="badge-telegram badge-telegram-dot"></span>
```

## Тестирование

1. Проверьте отображение при разных значениях: `1`, `5`, `12`, `99+`
2. Протестируйте анимации: `animate-in`, `pulse`
3. Проверьте адаптивность на мобильных устройствах
4. Убедитесь в правильности темной темы

## Совместимость

- ✅ Все современные браузеры
- ✅ Mobile Safari
- ✅ Chrome/Edge
- ✅ Firefox
- ✅ Светлая/темная темы

## Дополнительные ресурсы

- [Telegram Web K - GitHub](https://github.com/morethanwords/tweb)
- [Badge Styles - SCSS](https://github.com/morethanwords/tweb/blob/master/src/scss/partials/_badge.scss)
- [Dialog List Badges](https://github.com/morethanwords/tweb/blob/master/src/scss/partials/_chatlist.scss)
