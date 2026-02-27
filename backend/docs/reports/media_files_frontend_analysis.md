# Анализ реализации медиафайлов на фронтенде

**Дата:** 21 января 2026  
**Проверено:** Backend API vs Frontend реализация

---

## 📊 Резюме

**Статус:** ✅ **ВСЕ основные функции реализованы**

Фронтенд полностью поддерживает работу с медиафайлами согласно backend API.

---

## 🔍 Детальный анализ

### 1. ✅ Создание сообщения с файлами

**Backend API:** `POST /api/v1/communications/messages/`
- Принимает FormData с `file_0`, `file_1`, ...
- Возвращает сообщение с массивом `attachments`

**Frontend реализация:**
- **Файл:** `chatComposer.js` → `sendMessage()`
- **Код:**
  ```javascript
  const formData = new FormData(this.form);
  this.selectedFiles.forEach((entry, index) => {
      formData.append(`file_${index}`, entry.file, entry.file.name);
  });
  ```
- **Статус:** ✅ Реализовано полностью

---

### 2. ✅ Редактирование сообщения с файлами

**Backend API:** Двухэтапный процесс
1. `POST /api/v1/communications/messages/upload-temp/` → загрузка новых файлов
2. `PATCH /api/v1/communications/messages/{id}/` → обновление с `existing_attachment_ids`

**Frontend реализация:**
- **Файл:** `chatComposer.js` → `sendEdit()`
- **Логика:**
  ```javascript
  // Шаг 1: Загрузка новых файлов
  const uploadResponse = await fetch('/api/v1/communications/messages/upload-temp/', {
      method: 'POST',
      body: formData // новые файлы
  });
  
  // Получаем IDs новых файлов
  const newAttachmentIds = uploadData.attachment_ids;
  
  // Шаг 2: Отправка на редактирование
  await fetch(`/api/v1/communications/messages/${messageId}/`, {
      method: 'PATCH',
      body: JSON.stringify({
          content,
          existing_attachment_ids: [...existingIds, ...newAttachmentIds]
      })
  });
  ```
- **Статус:** ✅ Реализовано полностью (двухэтапный процесс)

---

### 3. ✅ Отображение вложений

**Backend API:** Возвращает массив `attachments` с полями:
```json
{
  "id": 123,
  "file_name": "photo.jpg",
  "file_type": "image",
  "file_url": "/media/chat_attachments/2026/01/21/photo.jpg",
  "file_size": 45678,
  "mime_type": "image/jpeg",
  "width": 1920,
  "height": 1080,
  "thumbnail": "/media/.../thumb.jpg"
}
```

**Frontend реализация:**
- **Файл:** `messageRendererV2.js` → `_renderAttachment()`
- **Типы файлов:**

#### 3.1. ✅ Изображения (image/*)
```javascript
if (fileType === 'image' || fileType.startsWith('image/')) {
    // Telegram approach: используем width/height для aspect-ratio
    const maxWidth = 500;
    const scale = Math.min(1, maxWidth / width);
    const w = Math.round(width * scale);
    const h = Math.round(height * scale);
    
    dimensionStyle = `style="width: ${w}px; height: ${h}px;"`;
    
    return `
        <a href="${fileUrl}" target="_blank" class="attachment-item attachment-item--media">
            <img src="${thumbnailUrl || fileUrl}" 
                 alt="${fileName}" 
                 class="chat-media chat-media--image"
                 ${dimensionStyle}
                 loading="lazy" />
        </a>
    `;
}
```
**Особенности:**
- ✅ Поддержка `thumbnail`
- ✅ Правильный `aspect-ratio` через `width/height` (как в Telegram)
- ✅ `loading="lazy"` для оптимизации
- ✅ Логирование загрузки изображений для отладки

#### 3.2. ✅ Видео (video/*)
```javascript
if (fileType === 'video' || fileType.startsWith('video/')) {
    return `
        <video src="${fileUrl}" 
               class="chat-media chat-media--video"
               controls
               playsinline
               preload="metadata">
        </video>
    `;
}
```
**Особенности:**
- ✅ HTML5 video с контролами
- ✅ `playsinline` для мобильных
- ✅ `preload="metadata"` для оптимизации

#### 3.3. ✅ Документы и другие файлы
```javascript
// Определяем иконку
let icon = 'bi-file-earmark';
if (fileType.includes('pdf')) icon = 'bi-file-pdf';
else if (fileType.includes('word')) icon = 'bi-file-word';
else if (fileType.startsWith('audio/')) icon = 'bi-file-music';

return `
    <a href="${fileUrl}" target="_blank" class="attachment-link">
        <i class="bi ${icon} me-2"></i>
        <span class="attachment-name">${fileName}</span>
        <span class="attachment-size">(${fileSizeStr})</span>
    </a>
`;
```
**Особенности:**
- ✅ Разные иконки для PDF, Word, Audio
- ✅ Отображение размера файла в KB
- ✅ Ссылка для скачивания

---

### 4. ✅ Превью файлов перед отправкой

**Frontend реализация:**
- **Файл:** `chatComposer.js` → `renderPreview()`
- **Локация:** `<div id="attachmentPreview">`

**Функции:**
```javascript
renderPreview() {
    this.selectedFiles.forEach((entry) => {
        const isImage = entry.file.type.startsWith('image/');
        const isExisting = entry.file._isExisting === true;
        
        // Для изображений - превью через URL.createObjectURL
        if (isImage) {
            const imgUrl = isExisting 
                ? entry.file._existingUrl  // Существующий файл
                : URL.createObjectURL(entry.file);  // Новый файл
            
            wrapper.innerHTML = `
                <img src="${imgUrl}" style="max-width: 60px; max-height: 60px;" />
                <div>${entry.file.name}</div>
                <div>${fileSizeStr}</div>
                <button data-file-id="${entry.id}">×</button>
            `;
        } else {
            // Для других файлов - иконка
            wrapper.innerHTML = `<i class="${iconClass}"></i> ...`;
        }
    });
}
```
**Особенности:**
- ✅ Превью изображений через blob URL
- ✅ Иконки для документов
- ✅ Отображение размера файла
- ✅ Кнопка удаления файла
- ✅ Поддержка существующих файлов при редактировании

---

### 5. ✅ Способы загрузки файлов

#### 5.1. ✅ Через кнопку "Прикрепить"
**HTML:**
```html
<button id="attachDocument">Документ</button> → #documentInput
<button id="attachImage">Изображение/Видео</button> → #imageInput
<button id="attachCamera">Камера</button> → #cameraInput
<button id="attachAudio">Аудио</button> → #audioInput
```

**JavaScript:**
```javascript
document.getElementById('attachImage').addEventListener('click', () => {
    document.getElementById('imageInput').click();
});
```

#### 5.2. ✅ Drag & Drop
```javascript
textarea.addEventListener('drop', (e) => {
    e.preventDefault();
    const files = Array.from(e.dataTransfer.files);
    files.forEach(file => {
        this.selectedFiles.push({ id: crypto.randomUUID(), file });
    });
    this.renderPreview();
});
```

#### 5.3. ✅ Вставка из буфера обмена (Paste)
```javascript
textarea.addEventListener('paste', (e) => {
    const items = Array.from(e.clipboardData.items);
    items.forEach(item => {
        if (item.kind === 'file') {
            const file = item.getAsFile();
            this.selectedFiles.push({ id: crypto.randomUUID(), file });
        }
    });
    this.renderPreview();
});
```

**Особенности:**
- ✅ Поддержка множественной загрузки (`multiple` для imageInput)
- ✅ Фильтрация по типу файла (`accept="image/*,video/*"`)
- ✅ Специальный режим камеры (`capture="environment"`)

---

### 6. ✅ Управление файлами

#### 6.1. Добавление файлов
```javascript
selectedFiles = [
    { id: 'uuid-1', file: File },
    { id: 'uuid-2', file: File },
    ...
]
```

#### 6.2. Удаление файла из превью
```javascript
removeFile(entryId) {
    this.selectedFiles = this.selectedFiles.filter(e => e.id !== entryId);
    this.renderPreview();
}
```

#### 6.3. Очистка после отправки
```javascript
resetForm() {
    this.selectedFiles = [];
    this.renderPreview();
    this.textarea.value = '';
}
```

---

### 7. ✅ Редактирование: Работа с существующими файлами

**Механизм:**
```javascript
// При загрузке для редактирования помечаем файлы как существующие
selectedFiles = [
    {
        id: 'existing-123',
        file: {
            name: 'photo.jpg',
            size: 45678,
            type: 'image/jpeg',
            _isExisting: true,          // ← Флаг
            _existingId: 123,            // ← ID в БД
            _existingUrl: '/media/...',  // ← URL для превью
            _sizeStr: '44.6 KB'          // ← Форматированный размер
        }
    }
];
```

**При отправке редактирования:**
```javascript
selectedFiles.forEach(entry => {
    if (entry.file._isExisting === true) {
        existingAttachmentIds.push(entry.file._existingId);
    } else {
        newFiles.push(entry);  // Загрузим через upload-temp
    }
});
```

---

## 🎯 Соответствие Backend API

| Backend функция | Frontend реализация | Статус |
|----------------|---------------------|---------|
| `POST /messages/` с `file_0, file_1` | ✅ `sendMessage()` → FormData | ✅ |
| `POST /messages/upload-temp/` | ✅ `sendEdit()` → шаг 1 | ✅ |
| `PATCH /messages/{id}/` + `existing_attachment_ids` | ✅ `sendEdit()` → шаг 2 | ✅ |
| Типы файлов: image, video, audio, file | ✅ `_renderAttachment()` | ✅ |
| `width`, `height` для aspect-ratio | ✅ Telegram approach | ✅ |
| `thumbnail` для изображений | ✅ Используется если есть | ✅ |
| `file_size`, `mime_type`, `file_name` | ✅ Отображаются | ✅ |

---

## ✨ Дополнительные возможности фронтенда

### Реализовано сверх требований:

1. ✅ **Drag & Drop** - перетаскивание файлов в textarea
2. ✅ **Paste** - вставка изображений из буфера обмена (Ctrl+V)
3. ✅ **Multiple upload** - загрузка нескольких файлов одновременно
4. ✅ **Preview с миниатюрами** - превью изображений перед отправкой
5. ✅ **Удаление из превью** - можно убрать файл до отправки
6. ✅ **Blob URL cleanup** - автоматическая очистка `URL.revokeObjectURL`
7. ✅ **Иконки по типам** - PDF, Word, Audio разные иконки
8. ✅ **Lazy loading** - `loading="lazy"` для изображений
9. ✅ **Telegram-стиль** - фиксированный aspect-ratio для изображений
10. ✅ **Capture API** - режим камеры для мобильных

---

## 🐛 Известные особенности

### 1. Отладочные логи
```javascript
console.log('[IMAGE DEBUG] Attachment #${attachmentId}:', {
    width, height,
    hasSize: !!(width && height),
    url: imgSrc
});
```
**Статус:** Можно оставить для отладки или удалить в продакшене

### 2. Редактирование файлов
- ✅ Можно добавлять новые файлы при редактировании
- ✅ Можно удалять существующие файлы
- ✅ Превью показывает и старые и новые файлы

---

## 📝 Выводы

### ✅ Реализовано на 100%

Все функции работы с медиафайлами из backend API **полностью реализованы** на фронтенде:

1. ✅ Загрузка файлов при создании сообщения
2. ✅ Редактирование сообщений с файлами (upload-temp + existing_attachment_ids)
3. ✅ Отображение всех типов вложений (image, video, audio, file)
4. ✅ Превью файлов перед отправкой
5. ✅ Управление файлами (добавление, удаление)
6. ✅ Поддержка метаданных (размер, MIME, thumbnail, width/height)

### 🎨 UX преимущества

- **Telegram-like** aspect-ratio для изображений
- **Drag & Drop** и **Paste** для удобства
- **Preview** перед отправкой
- **Multiple** загрузка файлов
- **Иконки** для разных типов файлов

### 🚀 Готовность

Система **полностью готова** к работе с медиафайлами без дополнительных доработок.

---

**Проверено:** Backend API ↔ Frontend реализация  
**Результат:** ✅ 100% соответствие
