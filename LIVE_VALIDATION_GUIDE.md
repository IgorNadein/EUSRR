# Live Validation - Валидация формы в реальном времени

## Описание

Модуль `liveValidationHandler.js` обеспечивает валидацию формы прямо в процессе ввода данных пользователем. Поля подсвечиваются зелёным (валидны) или красным (ошибки) с отображением сообщений об ошибках.

## Особенности

✅ **Валидация в реальном времени** - проверка при вводе с debounce  
✅ **Валидация при потере фокуса** - проверка когда пользователь покидает поле  
✅ **Валидация при отправке** - финальная проверка перед submit  
✅ **Красивая подсветка** - использует Bootstrap классы `.is-valid` / `.is-invalid`  
✅ **Умное поведение** - валидация начинается только после первого касания поля  
✅ **Debounce** - не спамит проверками при быстром вводе  
✅ **Связанные поля** - автоматически ревалидирует зависимые поля (например, password2 при изменении password1)

## Типы валидаторов

### 1. `required` - Обязательное поле
```javascript
{ type: 'required', message: 'Поле обязательно для заполнения' }
```

### 2. `email` - Email формат
```javascript
{ type: 'email', message: 'Введите корректный email' }
```

### 3. `pattern` - Регулярное выражение
```javascript
{ 
  type: 'pattern', 
  pattern: /^\+?\d{10,15}$/, 
  message: 'Неверный формат телефона' 
}
```

### 4. `minLength` / `maxLength` - Длина строки
```javascript
{ type: 'minLength', value: 6, message: 'Минимум 6 символов' }
{ type: 'maxLength', value: 100, message: 'Максимум 100 символов' }
```

### 5. `match` - Совпадение с другим полем
```javascript
{ 
  type: 'match', 
  field: 'password1', 
  message: 'Пароли не совпадают' 
}
```

### 6. `anyContact` - Хотя бы одно из полей заполнено
```javascript
{
  type: 'anyContact',
  fields: ['telegram', 'whatsapp', 'wechat'],
  message: 'Заполните хотя бы один мессенджер'
}
```

### 7. `custom` - Кастомная функция валидации
```javascript
{
  type: 'custom',
  validate: (value, formData, input) => {
    const date = new Date(value);
    const age = new Date().getFullYear() - date.getFullYear();
    return age >= 18 && age <= 100;
  },
  message: 'Возраст должен быть от 18 до 100 лет'
}
```

## Использование

### Базовая инициализация

```javascript
import { initLiveValidation } from './liveValidationHandler.js';

const validator = initLiveValidation({
  formSelector: '#myForm',
  rules: {
    email: [
      { type: 'required', message: 'Email обязателен' },
      { type: 'email', message: 'Некорректный email' }
    ],
    password: [
      { type: 'required', message: 'Пароль обязателен' },
      { type: 'minLength', value: 6, message: 'Минимум 6 символов' }
    ]
  }
});
```

### Расширенная конфигурация

```javascript
const validator = initLiveValidation({
  formSelector: 'form',
  debounce: 500,           // Задержка перед валидацией (мс)
  validateOnBlur: true,    // Валидировать при потере фокуса
  validateOnInput: true,   // Валидировать при вводе
  validateOnSubmit: true,  // Валидировать при отправке
  rules: {
    // ... правила
  }
});
```

## API методы

### `validateField(fieldName)`
Валидирует конкретное поле вручную:
```javascript
validator.validateField('email');
```

### `validateForm()`
Валидирует всю форму и возвращает результат:
```javascript
const isValid = validator.validateForm();
if (isValid) {
  console.log('Форма валидна!');
}
```

### `clearValidation()`
Очищает всю валидацию (убирает подсветку и сообщения):
```javascript
validator.clearValidation();
```

### `destroy()`
Удаляет все обработчики событий:
```javascript
validator.destroy();
```

## Пример интеграции с формой регистрации

```javascript
import { initLiveValidation } from './liveValidationHandler.js';

document.addEventListener('DOMContentLoaded', function () {
  const validator = initLiveValidation({
    formSelector: 'form',
    debounce: 500,
    rules: {
      email: [
        { type: 'required', message: 'Email обязателен' },
        { type: 'email', message: 'Введите корректный email' }
      ],
      password1: [
        { type: 'required', message: 'Пароль обязателен' },
        { type: 'minLength', value: 6, message: 'Минимум 6 символов' }
      ],
      password2: [
        { type: 'required', message: 'Подтвердите пароль' },
        { type: 'match', field: 'password1', message: 'Пароли не совпадают' }
      ]
    }
  });

  // Ревалидация password2 при изменении password1
  document.querySelector('[name="password1"]')?.addEventListener('input', () => {
    const password2 = document.querySelector('[name="password2"]');
    if (password2 && password2.value) {
      validator.validateField('password2');
    }
  });
});
```

## Как это выглядит

### До ввода
Поля обычные, без подсветки.

### Во время ввода (после первого blur)
- ✅ **Зелёная рамка** - поле валидно
- ❌ **Красная рамка** - есть ошибка
- 💬 **Текст ошибки** - красный текст под полем

### При отправке формы
- Все невалидные поля подсвечиваются красным
- Форма не отправляется если есть ошибки
- Фокус переходит на первое невалидное поле

## Совместимость с Bootstrap

Модуль использует стандартные Bootstrap классы:
- `.is-valid` - валидное поле
- `.is-invalid` - невалидное поле
- `.invalid-feedback` - контейнер для сообщения об ошибке

## Производительность

- **Debounce** предотвращает избыточные проверки при быстром вводе
- **Ленивая валидация** - поля проверяются только после первого blur
- **Умная ревалидация** - связанные поля (например, password2) обновляются автоматически

## Примечания

1. Валидация начинается **после первого blur** (потери фокуса) поля
2. После blur валидация работает **в реальном времени** при каждом вводе
3. Финальная валидация **всегда происходит** при submit формы
4. Можно комбинировать несколько правил для одного поля
5. Правила проверяются **последовательно**, первая ошибка останавливает проверку

## Интеграция с AJAX формами

Если форма отправляется через AJAX, можно использовать метод `validateForm()` перед отправкой:

```javascript
form.addEventListener('submit', async (e) => {
  e.preventDefault();
  
  if (!validator.validateForm()) {
    console.log('Форма содержит ошибки');
    return;
  }
  
  // Отправка через fetch
  const formData = new FormData(form);
  const response = await fetch('/api/register/', {
    method: 'POST',
    body: formData
  });
  
  // Обработка ответа...
});
```
