# Документы - Frontend Implementation

## Реализованный функционал

### 1. **Загрузка документов** (django-filer)

✅ Компонент `DocumentUploadForm`:
- Drag & Drop интерфейс для загрузки файлов
- Поддержка различных типов файлов (PDF, Word, Excel, изображения, текст)
- Валидация размера файлов
- Автоматическое заполнение названия из имени файла
- Форма с полями: название, тип, описание, теги
- Интеграция с API (`POST /api/v1/documents/`)

### 2. **FSM Workflow** (django-fsm)

✅ Компонент `DocumentStatusBadge`:
- Цветовые индикаторы для каждого статуса:
  * 🟢 Черновик (серый)
  * 🔵 На рассмотрении (голубой)
  * 🟢 Утверждено (зеленый)
  * 🔵 Опубликовано (синий)
  * ⚪ В архиве (серый)
  * 🔴 Отклонено (красный)

✅ Компонент `DocumentWorkflowButtons`:
- Динамические кнопки действий в зависимости от текущего статуса
- Переходы:
  * Черновик → Отправить на рассмотрение
  * На рассмотрении → Утвердить / Отклонить / Вернуть в черновик
  * Утверждено → Опубликовать
  * Опубликовано → Архивировать
  * В архиве → Разархивировать
- Подтверждающие диалоги для критичных действий
- Toast уведомления об успехе/ошибке

### 3. **Preview файлов**

✅ Компонент `DocumentPreview`:
- Встроенный просмотр PDF файлов с постраничной навигацией
- Использует `react-pdf` и `pdfjs-dist`
- Кнопки: следующая/предыдущая страница, скачать, закрыть
- Для не-PDF файлов: предложение скачать
- Полноэкранное модальное окно

### 4. **Подтверждение прочтения**

✅ Компонент `DocumentAcknowledgement`:
- Форма подтверждения с опциональным комментарием
- Индикатор "Прочитано" для текущего пользователя
- Список всех подтверждений с именами пользователей и датами
- Интеграция с API (`POST /api/v1/documents/{id}/acknowledge/`)

### 5. **Список документов**

✅ Обновленная страница `documents/page.tsx`:
- Поиск по названию, описанию, типу, автору
- Фильтрация по статусу (все/черновик/на рассмотрении/...)
- Карточки документов с:
  * Статус badge
  * Workflow кнопки
  * Теги
  * Метаданные (автор, даты)
  * Кнопки "Просмотр" и "Детали"
- Модальное окно с детальной информацией о документе
- Модальное окно загрузки нового документа

## API интеграция

### Обновленный `apiClient` (`lib/api.ts`)

Добавлены методы:

```typescript
// CRUD операции
getDocuments(params?) // GET /api/v1/documents/
getDocument(id) // GET /api/v1/documents/{id}/
createDocument(data) // POST /api/v1/documents/
updateDocument(id, data) // PATCH /api/v1/documents/{id}/
deleteDocument(id) // DELETE /api/v1/documents/{id}/

// FSM переходы
submitDocumentForReview(id) // POST /api/v1/documents/{id}/submit-for-review/
approveDocument(id) // POST /api/v1/documents/{id}/approve/
rejectDocument(id) // POST /api/v1/documents/{id}/reject/
publishDocument(id) // POST /api/v1/documents/{id}/publish/
returnDocumentToDraft(id) // POST /api/v1/documents/{id}/return-to-draft/
archiveDocument(id) // POST /api/v1/documents/{id}/archive/
unarchiveDocument(id) // POST /api/v1/documents/{id}/unarchive/

// Подтверждение прочтения
acknowledgeDocument(id, notes?) // POST /api/v1/documents/{id}/acknowledge/
```

## TypeScript типы

### Обновленный `types/api.ts`

```typescript
export type DocumentStatus = 
  | 'draft' 
  | 'in_review' 
  | 'approved' 
  | 'published' 
  | 'archived' 
  | 'rejected';

export interface DocumentAcknowledgement {
  id: number;
  document: number;
  user: User;
  acknowledged_at: string;
  notes?: string;
}

export interface Document {
  id: number;
  title: string;
  description?: string;
  file?: string;
  file_url?: string;
  file_name?: string;
  file_size?: number;
  document_type: string;
  status: string; // human-readable
  status_code: DocumentStatus; // machine-readable
  created_by: User;
  created_at: string;
  updated_at: string;
  tags?: string[];
  acknowledgements?: DocumentAcknowledgement[];
  acknowledgement_required?: boolean;
  is_acknowledged?: boolean;
}
```

## Установленные библиотеки

```json
{
  "dependencies": {
    "react-dropzone": "^14.2.3",
    "react-pdf": "^9.1.1",
    "pdfjs-dist": "^4.8.69",
    "react-file-icon": "^1.5.0",
    "@tanstack/react-table": "^8.20.5"
  }
}
```

## Структура файлов

```
frontend/src/
├── components/
│   └── documents/
│       ├── index.ts
│       ├── DocumentUploadForm.tsx
│       ├── DocumentStatusBadge.tsx
│       ├── DocumentWorkflowButtons.tsx
│       ├── DocumentPreview.tsx
│       └── DocumentAcknowledgement.tsx
├── app/
│   └── documents/
│       └── page.tsx (обновлена)
├── lib/
│   └── api.ts (обновлен)
└── types/
    └── api.ts (обновлен)
```

## Использование компонентов

### DocumentUploadForm

```tsx
import { DocumentUploadForm } from "@/components/documents";

<DocumentUploadForm
  onSuccess={() => {
    // Обновить список документов
  }}
  onCancel={() => {
    // Закрыть форму
  }}
/>
```

### DocumentStatusBadge

```tsx
import { DocumentStatusBadge } from "@/components/documents";

<DocumentStatusBadge
  status="На рассмотрении"
  statusCode="in_review"
/>
```

### DocumentWorkflowButtons

```tsx
import { DocumentWorkflowButtons } from "@/components/documents";

<DocumentWorkflowButtons
  documentId={doc.id}
  currentStatus={doc.status_code}
  onStatusChange={() => {
    // Обновить данные
  }}
/>
```

### DocumentPreview

```tsx
import { DocumentPreview } from "@/components/documents";

<DocumentPreview
  fileUrl="http://backend/media/documents/file.pdf"
  fileName="document.pdf"
  onClose={() => setShowPreview(false)}
/>
```

### DocumentAcknowledgement

```tsx
import { DocumentAcknowledgement } from "@/components/documents";

<DocumentAcknowledgement
  document={doc}
  onAcknowledge={() => {
    // Обновить данные
  }}
/>
```

## Roadmap / Будущие улучшения

### Приоритет ВЫСОКИЙ
- [ ] Добавить права доступа на UI уровне (скрывать кнопки для пользователей без прав)
- [ ] Версионирование документов (интеграция с django-reversion)
- [ ] История изменений статуса (timeline view)

### Приоритет СРЕДНИЙ
- [ ] Редактирование документов (обновление файла, метаданных)
- [ ] Массовые операции (архивирование нескольких документов)
- [ ] Экспорт списка документов (CSV, Excel)
- [ ] Уведомления о смене статуса

### Приоритет НИЗКИЙ
- [ ] OCR для сканов (pytesseract на бэкенде)
- [ ] Полнотекстовый поиск по содержимому PDF
- [ ] Интеграция с внешними хранилищами (Google Drive, OneDrive)
- [ ] Шаблоны документов

## Тестирование

### Checklist для проверки

- [ ] Загрузка документа через Drag & Drop
- [ ] Загрузка документа через выбор файла
- [ ] Поиск по документам
- [ ] Фильтрация по статусу
- [ ] Переход: Черновик → На рассмотрении
- [ ] Переход: На рассмотрении → Утверждено
- [ ] Переход: Утверждено → Опубликовано
- [ ] Preview PDF файла
- [ ] Подтверждение прочтения документа
- [ ] Просмотр списка подтверждений
- [ ] Модальное окно с деталями документа

## Известные проблемы

1. **PDF.js Worker Warning**: 
   - В консоли может появляться предупреждение о worker
   - Решение: уже настроен через unpkg CDN в `DocumentPreview.tsx`

2. **API Permission Tests**:
   - ~10 тестов в бэкенде падают (проблема с правами доступа)
   - Не блокирует работу frontend

## Контакты

Для вопросов и предложений обращайтесь к команде разработки.
