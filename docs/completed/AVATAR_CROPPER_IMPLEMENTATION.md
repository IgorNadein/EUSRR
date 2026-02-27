# Avatar Cropper Implementation for FaceID

## 📋 Описание

Реализован компонент обрезки аватара с требованиями для системы распознавания лиц (FaceID).

## 🎯 Цели

1. ✅ Обеспечить единообразие фотографий для FaceID
2. ✅ Гарантировать, что лицо занимает 70-80% кадра
3. ✅ Минимальный размер: 600x600px
4. ✅ Формат: JPEG с оптимизацией качества (92%)
5. ✅ Интеграция в 2 места: регистрация + редактор профиля

## 🔧 Технические детали

### Используемые технологии

- **Cropper.js v1.6.1** - библиотека для обрезки изображений
- **Bootstrap 5 Modal** - модальное окно
- **Canvas API** - конвертация в нужный формат
- **File API** - работа с файлами

### Компоненты

#### 1. **avatarCropperHandler.js** 
Основной модуль с классом `AvatarCropper`:

```javascript
import { initAvatarCropper } from '/static/js/components/avatarCropperHandler.js';

// Инициализация
initAvatarCropper({
  fileInputSelector: 'input[type="file"][name="avatar"]',
  previewImageId: 'avatarPreview',
  placeholderId: 'avatarPlaceholder',
  modalId: 'avatarCropperModal'
});
```

**Возможности:**
- ✅ Автоматическое открытие cropper при выборе файла
- ✅ Валидация размера и формата
- ✅ Квадратная область обрезки (1:1)
- ✅ Минимальный размер обрезки: 200x200px
- ✅ Выходной размер: 800x800px
- ✅ Качество JPEG: 92%
- ✅ Индикатор размера в реальном времени
- ✅ Превью обрезанного изображения
- ✅ Автоматическое обновление file input

### Интеграция

#### Место 1: Регистрация (`templates/auth/register.html`)

```html
<!-- Cropper.js CDN -->
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/cropperjs/1.6.1/cropper.min.css">
<script src="https://cdnjs.cloudflare.com/ajax/libs/cropperjs/1.6.1/cropper.min.js"></script>

<script type="module">
  import { initAvatarCropper } from "{% static 'js/components/avatarCropperHandler.js' %}";
  
  initAvatarCropper({
    fileInputSelector: 'input[type="file"][name="avatar"]',
    previewImageId: 'avatarPreview',
    placeholderId: 'avatarPlaceholder'
  });
</script>
```

#### Место 2: Редактор профиля (`templates/employees/components/employee_form_scripts.html`)

```html
<!-- Cropper.js CDN -->
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/cropperjs/1.6.1/cropper.min.css">
<script src="https://cdnjs.cloudflare.com/ajax/libs/cropperjs/1.6.1/cropper.min.js"></script>

<script type="module">
  import { initAvatarCropper } from '{% static "js/components/avatarCropperHandler.js" %}';
  
  initAvatarCropper({
    fileInputSelector: '#avatarInput',
    previewImageId: 'avatarPreview',
    modalId: 'avatarCropperModal'
  });
</script>
```

## 📝 Требования FaceID

### Обязательные требования:
1. ✅ **Размер лица**: 70-80% кадра
2. ✅ **Центрирование**: Лицо в центре рамки
3. ✅ **Минимальный размер**: 600x600px
4. ✅ **Соотношение сторон**: 1:1 (квадрат)
5. ✅ **Формат**: JPEG
6. ✅ **Качество**: 92%

### Рекомендации для пользователей:
- Избегайте теней и бликов
- Смотрите прямо в камеру
- Нейтральное выражение лица
- Хорошее освещение

## 🎨 UI/UX

### Модальное окно cropper

```
┌─────────────────────────────────────────┐
│ Обрезка фото для FaceID            [X] │
├─────────────────────────────────────────┤
│                                         │
│  ℹ️ Требования для системы распознавания:│
│  • Лицо должно занимать 70-80% кадра   │
│  • Расположите лицо в центре рамки     │
│  • Избегайте теней и бликов            │
│  • Смотрите прямо в камеру             │
│  • Нейтральное выражение лица          │
│                                         │
│  ┌───────────────────────────────────┐ │
│  │                                   │ │
│  │     [Cropper Canvas Area]         │ │
│  │                                   │ │
│  └───────────────────────────────────┘ │
│                                         │
│  Размер обрезанного фото: 800x800px    │
│                                         │
├─────────────────────────────────────────┤
│              [Отмена] [✓ Применить]    │
└─────────────────────────────────────────┘
```

### Превью в форме

- **До выбора**: Иконка placeholder (bi-person или bi-person-circle)
- **После обрезки**: Обрезанное изображение 120x120px
- **Подсказка**: Текст с требованиями FaceID

## 🚀 Workflow

### Шаг 1: Пользователь выбирает файл
```
Input[type=file] → change event
```

### Шаг 2: Валидация
```javascript
✓ Формат: JPG, PNG, GIF
✓ Размер: < 10 MB
✓ Минимальный размер: 600x600px
```

### Шаг 3: Открытие Cropper
```
FileReader → DataURL → Modal → Cropper.js init
```

### Шаг 4: Обрезка
```
User adjusts crop area → Real-time size indicator
```

### Шаг 5: Применение
```
getCroppedCanvas(800x800) → Blob → File → Update input
```

### Шаг 6: Превью
```
Canvas → DataURL → Update preview image
```

### Шаг 7: Отправка формы
```
FormData with cropped file → Backend API
```

## 📊 Конфигурация

### Настройки по умолчанию:

```javascript
{
  // Cropper.js options
  aspectRatio: 1,
  viewMode: 2,
  dragMode: 'move',
  autoCropArea: 0.8,
  minCropBoxWidth: 200,
  minCropBoxHeight: 200,
  
  // Output settings
  minOutputSize: 600,
  outputSize: 800,
  outputQuality: 0.92,
  outputFormat: 'image/jpeg',
  
  // Validation
  maxFileSize: 10 * 1024 * 1024, // 10 MB
  allowedFormats: ['image/jpeg', 'image/png', 'image/gif']
}
```

### Кастомизация:

```javascript
initAvatarCropper({
  // Селекторы
  fileInputSelector: '#myAvatarInput',
  previewImageId: 'myPreview',
  modalId: 'myCropperModal',
  
  // Cropper опции
  cropperOptions: {
    aspectRatio: 1,
    autoCropArea: 0.9
  },
  
  // Выходные параметры
  outputSize: 1024,
  outputQuality: 0.95,
  
  // Тексты
  texts: {
    modalTitle: 'Обрезать фото',
    cropButton: 'Готово',
    cancelButton: 'Отмена'
  }
});
```

## 🧪 Тестирование

### Тестовые сценарии:

1. **Регистрация нового пользователя**
   - Открыть `/auth/register/`
   - Выбрать фото
   - Проверить открытие cropper
   - Обрезать фото
   - Отправить форму
   - Проверить, что аватар сохранился

2. **Редактирование профиля**
   - Открыть `/employees/profile/`
   - Выбрать новое фото
   - Обрезать фото
   - Сохранить изменения
   - Проверить обновление аватара

3. **Валидация**
   - Попытаться загрузить файл < 600x600px → Ошибка
   - Попытаться загрузить файл > 10MB → Ошибка
   - Попытаться загрузить .txt файл → Ошибка

4. **Отмена**
   - Выбрать фото
   - Открыть cropper
   - Нажать "Отмена"
   - Проверить, что input очищен

## 📦 Зависимости

### CDN (используется):
```html
<!-- Cropper.js CSS -->
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/cropperjs/1.6.1/cropper.min.css" 
      integrity="sha512-hvNR0F/e2J7zPPfLC9auFe3/SE0yG4aJCOd/qxew74NN7eyiSKjr7xJJMu1Jy2wf7FXITpWS1E/RY8yzuXN7VA==" 
      crossorigin="anonymous" referrerpolicy="no-referrer" />

<!-- Cropper.js JS -->
<script src="https://cdnjs.cloudflare.com/ajax/libs/cropperjs/1.6.1/cropper.min.js" 
        integrity="sha512-9KkIqdfN7ipEW6B6k+Aq20PV31bjODg4AA52W+tYtAE0jE0kMx49bjJ3FgvS56wzmyfMUHbQ4Km2b7l9+Y/+Eg==" 
        crossorigin="anonymous" referrerpolicy="no-referrer"></script>
```

### Существующие зависимости:
- ✅ Bootstrap 5 (для модального окна)
- ✅ Bootstrap Icons (для иконок)

## 🔍 Troubleshooting

### Проблема: Cropper не открывается
**Решение:** Проверьте, что Cropper.js загружен из CDN и Bootstrap модальные окна работают.

### Проблема: File input не обновляется
**Решение:** Проверьте console на ошибки. Убедитесь, что DataTransfer API поддерживается.

### Проблема: Превью не обновляется
**Решение:** Проверьте селекторы `previewImageId` и `placeholderId`.

### Проблема: Ошибка "Image too small"
**Решение:** Убедитесь, что исходное изображение >= 600x600px.

## ✅ Checklist

### Файлы созданы:
- ✅ `backend/static/js/components/avatarCropperHandler.js` (542 строки)
- ✅ `AVATAR_CROPPER_IMPLEMENTATION.md` (этот файл)

### Файлы изменены:
- ✅ `backend/templates/auth/register.html` - добавлен cropper
- ✅ `backend/templates/employees/components/employee_form_scripts.html` - добавлен cropper
- ✅ `backend/templates/employees/components/employee_form_personal.html` - обновлен текст подсказки

### Функционал:
- ✅ Валидация размера файла (10 MB)
- ✅ Валидация формата (JPG, PNG, GIF)
- ✅ Валидация минимального размера (600x600px)
- ✅ Cropper с квадратной областью (1:1)
- ✅ Индикатор размера в реальном времени
- ✅ Превью обрезанного изображения
- ✅ Обновление file input
- ✅ Инструкции для FaceID
- ✅ Модальное окно Bootstrap
- ✅ Обработка ошибок
- ✅ Cleanup при закрытии

## 🎉 Готово к тестированию!

Все изменения в ветке `feature/avatar-validation`.

**Следующие шаги:**
1. Тестирование на локальном сервере
2. Проверка валидации
3. Проверка сохранения аватара
4. Коммит и push изменений
5. Создание PR в master (после тестирования)
