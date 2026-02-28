# План реализации DMS уровня Mayan EDMS

**Цель:** Создать корпоративную систему управления документами не ниже Mayan EDMS

**Дата начала:** 28 февраля 2026 г.

---

## 🎯 Ключевые возможности Mayan EDMS для реализации:

1. ✅ **Document Storage** - django-filer + metadata
2. ✅ **Full-text Search** - django-watson + client-side
3. ✅ **OCR** - Tesseract.js (client-side)
4. ✅ **Versioning** - django-reversion
5. ✅ **Workflow** - django-fsm + визуализация
6. ✅ **Permissions** - django-rules + filer ACL
7. ✅ **Folders/Cabinets** - filer.Folder + Tags
8. ✅ **PDF Operations** - pdf-lib (client-side)
9. ✅ **Notifications** - существующая система
10. ✅ **REST API** - DRF
11. ✅ **Modern UI** - Next.js + React

---

## 📋 PHASE 1: Backend Foundation (2-3 дня)

### 1.1 Document Model Enhancement
- [x] Добавить поле `folder` (уже сделано)
- [ ] Добавить `extracted_text` для full-text search
- [ ] Добавить `document_type` FK
- [ ] Добавить `tags` M2M
- [ ] Интегрировать с django-watson
- [ ] Добавить django-reversion

### 1.2 Additional Models
- [ ] `DocumentType` - типы документов с JSON schema метаданных
- [ ] `DocumentMetadata` - динамические key-value метаданные
- [ ] `DocumentTag` - теги для категоризации
- [ ] `Cabinet` - виртуальные хранилища (MPTT)
- [ ] `DocumentAuditLog` - полный аудит действий

### 1.3 Serializers & API
- [ ] Расширить `DocumentReadSerializer` (folder, tags, metadata)
- [ ] Создать `FolderSerializer` для filer.Folder
- [ ] Создать `DocumentTypeSerializer`
- [ ] Создать `TagSerializer`
- [ ] API endpoint: `/folders/` (tree view)
- [ ] API endpoint: `/document-types/`
- [ ] API endpoint: `/tags/`
- [ ] API endpoint: `/documents/{id}/versions/`
- [ ] API endpoint: `/documents/{id}/audit-log/`

### 1.4 File Browser UI Integration
- [ ] Подключить `filer.server.urls` для админки
- [ ] Настроить FILER_* settings
- [ ] Протестировать File Browser

### 1.5 Search Integration
- [ ] Зарегистрировать Document в watson
- [ ] API endpoint: `/search/?q=...`
- [ ] Фильтры по типу, дате, статусу

**Результат Phase 1:** Полноценный backend API с папками, поиском, версионированием

---

## 📋 PHASE 2: Frontend Foundation (2-3 дня)

### 2.1 Install Dependencies
```bash
cd frontend
npm install tesseract.js pdf-lib mammoth fuse.js reactflow recharts react-signature-canvas dnd-kit
```

### 2.2 Core Components Structure
```
src/components/documents/
  ├── browser/
  │   ├── FolderTree.tsx          # Древовидная навигация
  │   ├── DocumentGrid.tsx        # Grid view документов
  │   ├── DocumentList.tsx        # List view документов
  │   └── Breadcrumbs.tsx         # Навигация
  ├── upload/
  │   ├── UploadZone.tsx          # Drag & drop + processing
  │   ├── ProcessingProgress.tsx  # Status bar обработки
  │   └── FilePreview.tsx         # Preview перед загрузкой
  ├── viewer/
  │   ├── PDFViewer.tsx           # Улучшенный PDF viewer
  │   ├── ImageViewer.tsx         # Lightbox для изображений
  │   └── DocumentPreview.tsx     # Quick preview modal
  ├── search/
  │   ├── SearchBar.tsx           # Поиск с автодополнением
  │   ├── SearchFilters.tsx       # Фильтры
  │   └── SearchResults.tsx       # Результаты с подсветкой
  └── metadata/
      ├── DocumentEditor.tsx      # Форма редактирования
      ├── MetadataForm.tsx        # Динамические метаданные
      └── TagsInput.tsx           # Теги с автодополнением
```

### 2.3 API Client Extension
- [ ] Расширить `apiClient` методами для folders
- [ ] Методы для tags
- [ ] Методы для document types
- [ ] Методы для versions
- [ ] Methods для audit log

### 2.4 TypeScript Types
- [ ] `Folder` interface
- [ ] `DocumentType` interface
- [ ] `Tag` interface
- [ ] `DocumentMetadata` interface
- [ ] `AuditLogEntry` interface

**Результат Phase 2:** Базовый File Browser с навигацией и загрузкой

---

## 📋 PHASE 3: Client-side Processing (2-3 дня)

### 3.1 OCR Integration (Tesseract.js)
```typescript
// src/lib/ocr.ts
import Tesseract from 'tesseract.js';

export async function performOCR(
  file: File,
  onProgress?: (progress: number) => void
): Promise<string> {
  const { data: { text } } = await Tesseract.recognize(
    file,
    'rus+eng',
    { logger: m => onProgress?.(m.progress * 100) }
  );
  return text;
}
```

### 3.2 PDF Text Extraction
```typescript
// src/lib/pdf-utils.ts
import * as pdfjsLib from 'pdfjs-dist';

export async function extractPDFText(file: File): Promise<string> {
  // ... implementation
}

export async function generatePDFThumbnail(file: File): Promise<string> {
  // ... implementation
}
```

### 3.3 PDF Operations (pdf-lib)
```typescript
// src/lib/pdf-operations.ts
import { PDFDocument } from 'pdf-lib';

export async function splitPDF(file: File, pages: number[]): Promise<Uint8Array>
export async function mergePDFs(files: File[]): Promise<Uint8Array>
export async function rotatePDF(file: File, rotation: number): Promise<Uint8Array>
```

### 3.4 Image Processing
```typescript
// src/lib/image-utils.ts
export async function compressImage(file: File, maxSizeMB: number): Promise<Blob>
export async function cropImage(file: File, area: CropArea): Promise<Blob>
export async function rotateImage(file: File, degrees: number): Promise<Blob>
```

### 3.5 DOCX Extraction
```typescript
// src/lib/docx-utils.ts
import mammoth from 'mammoth';

export async function extractDOCXText(file: File): Promise<string>
```

### 3.6 Enhanced Upload Flow
- [ ] Pre-processing перед загрузкой
- [ ] Progress indicators для каждого этапа
- [ ] Preview extracted text
- [ ] Automatic title suggestion
- [ ] Validation на клиенте

**Результат Phase 3:** Полная client-side обработка файлов

---

## 📋 PHASE 4: Advanced Features (3-4 дня)

### 4.1 Enhanced PDF Viewer
- [ ] Page navigation (prev/next)
- [ ] Zoom controls (fit-width, fit-page, custom)
- [ ] Rotation
- [ ] Thumbnail sidebar
- [ ] Page search
- [ ] Print functionality

### 4.2 PDF Annotations
```typescript
// src/components/documents/viewer/PDFAnnotations.tsx
- [ ] Drawing tools (pen, highlighter, shapes)
- [ ] Text annotations
- [ ] Sticky notes
- [ ] Save/Load annotations
- [ ] Export annotated PDF
```

### 4.3 Advanced Search
- [ ] Fuzzy search (Fuse.js)
- [ ] Search в extracted_text с подсветкой
- [ ] Фильтры: дата, тип, автор, статус, теги
- [ ] Сохраненные поиски (localStorage)
- [ ] Recent searches

### 4.4 Batch Operations
- [ ] Multiple select (checkboxes)
- [ ] Bulk move to folder
- [ ] Bulk add tags
- [ ] Bulk change status
- [ ] Bulk delete
- [ ] Progress indicator

### 4.5 Dashboard & Analytics
```typescript
// src/app/documents/dashboard/page.tsx
- [ ] Статистика: всего документов, по типам, по статусам
- [ ] Recent uploads (chart)
- [ ] Top tags cloud
- [ ] Activity feed
- [ ] My documents / Favorites
```

**Результат Phase 4:** Rich UI с расширенными возможностями

---

## 📋 PHASE 5: Workflow & Permissions (2-3 дня)

### 5.1 Workflow Visualization
```typescript
// src/components/documents/workflow/WorkflowDiagram.tsx
- [ ] React Flow диаграмма states/transitions
- [ ] Highlight current state
- [ ] Show available transitions
- [ ] Timeline история переходов
```

### 5.2 Workflow Actions UI
- [ ] Кнопки transitions (уже есть базово)
- [ ] Modal с комментарием при переходе
- [ ] Assignee selection (кому назначить)
- [ ] Due date для review

### 5.3 Permissions UI
```typescript
// src/components/documents/permissions/PermissionsEditor.tsx
- [ ] User/Group selector
- [ ] Permission checkboxes (view, download, edit, delete)
- [ ] Inheritance от папки
- [ ] ACL list display
```

### 5.4 Version History
```typescript
// src/components/documents/versions/VersionHistory.tsx
- [ ] Timeline версий
- [ ] Diff viewer (сравнение метаданных)
- [ ] Download старой версии
- [ ] Restore к предыдущей версии
```

### 5.5 Audit Log Viewer
```typescript
// src/components/documents/audit/AuditLog.tsx
- [ ] Timeline всех действий
- [ ] Filter: action type, user, date range
- [ ] Export audit log
```

**Результат Phase 5:** Полный workflow + права + аудит

---

## 📋 PHASE 6: Polish & Production (2-3 дня)

### 6.1 Digital Signatures
- [ ] Backend: создание/проверка подписи
- [ ] Frontend: signature pad component
- [ ] Certificate upload/management
- [ ] Visual indicator подписанных документов

### 6.2 Performance Optimization
- [ ] Lazy loading компонентов
- [ ] Virtual scrolling для больших списков (@tanstack/react-virtual)
- [ ] Image lazy loading
- [ ] API response caching (React Query)
- [ ] Debouncing search

### 6.3 Offline Support
- [ ] Service Worker
- [ ] IndexedDB для offline documents
- [ ] Sync queue для offline uploads

### 6.4 Mobile Responsive
- [ ] Adaptive layout
- [ ] Touch gestures для PDF viewer
- [ ] Mobile upload (camera)

### 6.5 Testing
- [ ] Backend: pytest для API
- [ ] Frontend: Jest + React Testing Library
- [ ] E2E: Playwright

### 6.6 Documentation
- [ ] API documentation (Swagger/ReDoc)
- [ ] User guide
- [ ] Admin guide
- [ ] Developer guide

**Результат Phase 6:** Production-ready система

---

## 🔄 Итеративная разработка:

Каждая фаза:
1. **Разработка** функциональности
2. **Тестирование** 
3. **Документирование**
4. **Коммит** в git
5. **Демо** пользователю

---

## 📊 Метрики успеха (сравнение с Mayan EDMS):

| Функция | Mayan EDMS | Наша система | Статус |
|---------|------------|--------------|--------|
| Document Storage | ✅ | 🔄 In progress | Phase 1 |
| Folders/Cabinets | ✅ | 🔄 In progress | Phase 1 |
| OCR | ✅ (server) | ✅ (client) | Phase 3 |
| Full-text Search | ✅ | 🔄 In progress | Phase 1 |
| Workflow | ✅ | 🔄 In progress | Phase 5 |
| Permissions | ✅ | 🔄 In progress | Phase 5 |
| Versioning | ✅ | 🔄 In progress | Phase 1 |
| Tags/Metadata | ✅ | 🔄 In progress | Phase 1 |
| Digital Signatures | ✅ | ⏳ Planned | Phase 6 |
| REST API | ✅ | 🔄 In progress | Phase 1 |
| Modern UI | ❌ | ✅ | Phase 2-4 |
| Client-side Processing | ❌ | ✅ | Phase 3 |
| PDF Viewer | ✅ | ✅ (better) | Phase 4 |
| Annotations | ✅ | ⏳ Planned | Phase 4 |
| Dashboard | ✅ | ⏳ Planned | Phase 4 |

**Преимущества над Mayan:**
- ✅ Современный React UI вместо Django templates
- ✅ Client-side processing (быстрее, не нагружает сервер)
- ✅ TypeScript безопасность
- ✅ Better UX (real-time feedback, progressive enhancement)

---

## ⏱️ Общая оценка времени:

- **Phase 1:** 2-3 дня (Backend Foundation)
- **Phase 2:** 2-3 дня (Frontend Foundation)
- **Phase 3:** 2-3 дня (Client-side Processing)
- **Phase 4:** 3-4 дня (Advanced Features)
- **Phase 5:** 2-3 дня (Workflow & Permissions)
- **Phase 6:** 2-3 дня (Polish & Production)

**Total: 13-19 дней чистой разработки**

---

## 🚀 Начинаем с Phase 1!

Следующие шаги:
1. ✅ Расширить модель Document
2. ✅ Создать дополнительные модели
3. ✅ Интегрировать django-watson
4. ✅ Создать API endpoints
5. ✅ Подключить File Browser
