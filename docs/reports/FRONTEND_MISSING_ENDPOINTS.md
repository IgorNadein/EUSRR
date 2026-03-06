# Отчет: Недостающие эндпоинты на фронтенде

**Дата:** 28 февраля 2026  
**Статус:** Анализ завершен  
**Файл API клиента:** `frontend/src/lib/api.ts`

---

## 📋 Резюме

Из **30+ новых эндпоинтов**, добавленных в бэкенд, на фронтенде **НЕ реализовано ни одного**. Все новые возможности требуют интеграции.

### Текущее состояние фронтенда

✅ **Реализовано:**
- Базовые CRUD операции с документами
- FSM workflow transitions (submit, approve, reject, publish, archive)
- Работа с папками (folders)
- Система ознакомления (acknowledgements)

❌ **НЕ реализовано:**
- Версионирование документов (django-reversion)
- Миниатюры изображений
- Связанные документы
- Теги документов
- Типы документов
- Виртуальные кабинеты
- Комментарии к документам с поддержкой threading

---

## 1️⃣ Версионирование документов (django-reversion)

### Эндпоинты бэкенда
```typescript
GET  /api/v1/documents/{id}/versions/      // История версий
GET  /api/v1/documents/{id}/activity/      // Временная шкала активности
POST /api/v1/documents/{id}/revert/        // Откат к версии
```

### Не реализовано на фронтенде
- [ ] Метод `getDocumentVersions(id: number)` 
- [ ] Метод `getDocumentActivity(id: number)`
- [ ] Метод `revertDocumentToVersion(id: number, versionId: number)`

### Типы TypeScript (требуется добавить)
```typescript
export interface DocumentVersion {
  id: number;
  revision_id: number;
  version: number;
  created_at: string;
  user: string;
  comment: string;
  changes: Record<string, any>;
}

export interface DocumentActivity {
  id: number;
  timestamp: string;
  user: string;
  action: string;
  description: string;
  related_object?: any;
}
```

### UI компоненты (отсутствуют)
- [ ] `DocumentVersionHistory.tsx` - список версий с diff
- [ ] `DocumentActivityTimeline.tsx` - временная шкала
- [ ] `VersionCompareModal.tsx` - сравнение версий
- [ ] `RevertConfirmDialog.tsx` - подтверждение отката

### Приоритет: **ВЫСОКИЙ**
Версионирование критично для аудита и восстановления данных.

---

## 2️⃣ Миниатюры документов

### Эндпоинты бэкенда
```typescript
GET /api/v1/documents/{id}/thumbnail/?size={small|medium|large|original}
```

### Не реализовано на фронтенде
- [ ] Метод `getDocumentThumbnail(id: number, size?: 'small' | 'medium' | 'large' | 'original')`
- [ ] Компонент `DocumentThumbnail.tsx`
- [ ] Хук `useDocumentThumbnail(id: number)`

### Использование (когда будет реализовано)
```typescript
// Пример
const thumbnailUrl = await api.getDocumentThumbnail(123, 'medium');

// Или в компоненте
<DocumentThumbnail documentId={123} size="medium" />
```

### UI улучшения
- [ ] Превью документов в списке (grid/card view)
- [ ] Галерея миниатюр в просмотре документа
- [ ] Lazy loading для миниатюр
- [ ] Placeholder при загрузке

### Приоритет: **СРЕДНИЙ**
Улучшает UX, но не критично для функциональности.

---

## 3️⃣ Связанные документы

### Эндпоинты бэкенда
```typescript
GET    /api/v1/documents/{id}/related/              // Список связанных
POST   /api/v1/documents/{id}/add_related/          // Добавить связь
DELETE /api/v1/documents/{id}/remove_related/       // Удалить связь
```

### Не реализовано на фронтенде
- [ ] Метод `getRelatedDocuments(id: number)`
- [ ] Метод `addRelatedDocument(id: number, relatedId: number)`
- [ ] Метод `removeRelatedDocument(id: number, relatedId: number)`

### Типы TypeScript
```typescript
export interface RelatedDocument {
  id: number;
  title: string;
  file_type: string;
  created_at: string;
  uploaded_by: string;
}
```

### UI компоненты
- [ ] `RelatedDocumentsList.tsx` - список связанных документов
- [ ] `AddRelatedDocumentModal.tsx` - поиск и добавление связей
- [ ] `RelatedDocumentsCard.tsx` - карточка на странице документа

### Приоритет: **ВЫСОКИЙ**
Важно для навигации и связывания информации.

---

## 4️⃣ Теги документов

### Эндпоинты бэкенда
```typescript
GET    /api/v1/document-tags/                       // Список всех тегов
POST   /api/v1/document-tags/                       // Создать тег
GET    /api/v1/document-tags/{id}/                  // Получить тег
PATCH  /api/v1/document-tags/{id}/                  // Обновить тег
DELETE /api/v1/document-tags/{id}/                  // Удалить тег
GET    /api/v1/document-tags/{id}/documents/        // Документы с тегом
```

### Не реализовано на фронтенде
- [ ] Метод `getDocumentTags()`
- [ ] Метод `createDocumentTag(data: { name: string; color?: string })`
- [ ] Метод `updateDocumentTag(id: number, data: Partial<DocumentTag>)`
- [ ] Метод `deleteDocumentTag(id: number)`
- [ ] Метод `getDocumentsByTag(tagId: number)`

### Типы TypeScript
```typescript
export interface DocumentTag {
  id: number;
  name: string;
  slug: string;
  color?: string;
  created_at: string;
  documents_count: number;
}
```

### UI компоненты
- [ ] `TagManager.tsx` - управление тегами
- [ ] `TagSelect.tsx` - выбор тегов (multi-select)
- [ ] `TagBadge.tsx` - отображение тега
- [ ] `TagFilter.tsx` - фильтр по тегам
- [ ] Интеграция в `DocumentForm.tsx`

### Приоритет: **ВЫСОКИЙ**
Теги критичны для организации и поиска документов.

---

## 5️⃣ Типы документов

### Эндпоинты бэкенда
```typescript
GET    /api/v1/document-types/                      // Список типов
POST   /api/v1/document-types/                      // Создать тип
GET    /api/v1/document-types/{id}/                 // Получить тип
PATCH  /api/v1/document-types/{id}/                 // Обновить тип
DELETE /api/v1/document-types/{id}/                 // Удалить тип
GET    /api/v1/document-types/{id}/documents/       // Документы типа
```

### Не реализовано на фронтенде
- [ ] Метод `getDocumentTypes()`
- [ ] Метод `createDocumentType(data: { name: string })`
- [ ] Метод `updateDocumentType(id: number, data: Partial<DocumentType>)`
- [ ] Метод `deleteDocumentType(id: number)`
- [ ] Метод `getDocumentsByType(typeId: number)`

### Типы TypeScript
```typescript
export interface DocumentType {
  id: number;
  name: string;
  slug: string;
  description?: string;
  icon?: string;
  created_at: string;
  documents_count: number;
}
```

### UI компоненты
- [ ] `DocumentTypeManager.tsx` - управление типами
- [ ] `DocumentTypeSelect.tsx` - выбор типа документа
- [ ] `DocumentTypeCard.tsx` - карточка типа
- [ ] Интеграция в `DocumentForm.tsx`

### Приоритет: **СРЕДНИЙ**
Типы полезны для категоризации, но есть альтернативы (теги, папки).

---

## 6️⃣ Виртуальные кабинеты (Cabinets)

### Эндпоинты бэкенда
```typescript
GET    /api/v1/cabinets/                            // Список кабинетов
POST   /api/v1/cabinets/                            // Создать кабинет
GET    /api/v1/cabinets/{id}/                       // Получить кабинет
PATCH  /api/v1/cabinets/{id}/                       // Обновить кабинет
DELETE /api/v1/cabinets/{id}/                       // Удалить кабинет
GET    /api/v1/cabinets/{id}/documents/             // Документы в кабинете
POST   /api/v1/cabinets/{id}/add_document/          // Добавить документ
POST   /api/v1/cabinets/{id}/remove_document/       // Удалить документ
GET    /api/v1/cabinets/{id}/children/              // Дочерние кабинеты
GET    /api/v1/cabinets/{id}/hierarchy/             // Полная иерархия
```

### Не реализовано на фронтенде
- [ ] Метод `getCabinets()`
- [ ] Метод `createCabinet(data: CreateCabinetData)`
- [ ] Метод `updateCabinet(id: number, data: Partial<Cabinet>)`
- [ ] Метод `deleteCabinet(id: number)`
- [ ] Метод `getCabinetDocuments(id: number)`
- [ ] Метод `addDocumentToCabinet(cabinetId: number, documentId: number)`
- [ ] Метод `removeDocumentFromCabinet(cabinetId: number, documentId: number)`
- [ ] Метод `getCabinetChildren(id: number)`
- [ ] Метод `getCabinetHierarchy(id: number)`

### Типы TypeScript
```typescript
export interface Cabinet {
  id: number;
  name: string;
  slug: string;
  description?: string;
  parent?: number;
  created_by: number;
  created_at: string;
  documents_count: number;
  children_count: number;
}

export interface CabinetHierarchy {
  id: number;
  name: string;
  parent: number | null;
  children: CabinetHierarchy[];
}
```

### UI компоненты
- [ ] `CabinetBrowser.tsx` - дерево кабинетов
- [ ] `CabinetCard.tsx` - карточка кабинета
- [ ] `CabinetForm.tsx` - форма создания/редактирования
- [ ] `AddToCabinetModal.tsx` - добавление документа в кабинет
- [ ] `CabinetBreadcrumbs.tsx` - навигация по иерархии
- [ ] Новый раздел в sidebar для кабинетов

### Приоритет: **СРЕДНИЙ**
Альтернатива Folders, но с дополнительными возможностями (M2M связи).

---

## 7️⃣ Комментарии к документам

### Эндпоинты бэкенда
```typescript
GET    /api/v1/document-comments/                   // Список комментариев
POST   /api/v1/document-comments/                   // Создать комментарий
GET    /api/v1/document-comments/{id}/              // Получить комментарий
PATCH  /api/v1/document-comments/{id}/              // Обновить комментарий
DELETE /api/v1/document-comments/{id}/              // Удалить комментарий
GET    /api/v1/document-comments/{id}/replies/      // Ответы на комментарий
```

### Не реализовано на фронтенде
- [ ] Метод `getDocumentComments(documentId: number)`
- [ ] Метод `createDocumentComment(data: CreateCommentData)`
- [ ] Метод `updateDocumentComment(id: number, text: string)`
- [ ] Метод `deleteDocumentComment(id: number)`
- [ ] Метод `getCommentReplies(commentId: number)`

### Типы TypeScript
```typescript
export interface DocumentComment {
  id: number;
  document: number;
  author: {
    id: number;
    full_name: string;
    avatar?: string;
  };
  text: string;
  parent?: number;
  created_at: string;
  updated_at: string;
  replies_count: number;
  can_edit: boolean;
  can_delete: boolean;
}

export interface CreateCommentData {
  document: number;
  text: string;
  parent?: number;
}
```

### UI компоненты
- [ ] `DocumentComments.tsx` - список комментариев
- [ ] `CommentItem.tsx` - отдельный комментарий
- [ ] `CommentForm.tsx` - форма добавления/редактирования
- [ ] `CommentThread.tsx` - ветка ответов (threading)
- [ ] `CommentReplyForm.tsx` - форма ответа на комментарий
- [ ] Уведомления о новых комментариях (интеграция с WebSocket)

### Приоритет: **ВЫСОКИЙ**
Комментарии важны для обсуждения документов и коллаборации.

---

## 📊 Приоритизация реализации

### Фаза 1: Критичные фичи (2-3 недели)
**Цель:** Основные возможности для работы с документами

1. ✅ **Комментарии к документам** (3-5 дней)
   - Базовый UI для комментариев
   - Поддержка threading (ответы)
   - Интеграция с уведомлениями

2. ✅ **Теги документов** (2-3 дня)
   - CRUD операции с тегами
   - Фильтр по тегам в списке документов
   - Multi-select в форме документа

3. ✅ **Связанные документы** (2-3 дня)
   - Просмотр связанных документов
   - Добавление/удаление связей
   - UI на странице документа

4. ✅ **Версионирование** (3-4 дня)
   - История версий с diff
   - Временная шкала активности
   - Откат к предыдущей версии

### Фаза 2: Полезные улучшения (1-2 недели)

5. ✅ **Миниатюры** (1-2 дня)
   - API метод для получения thumbnail
   - Компонент для отображения
   - Интеграция в списки документов

6. ✅ **Типы документов** (2-3 дня)
   - Управление типами
   - Фильтр по типу
   - Иконки для типов

### Фаза 3: Дополнительные возможности (1-2 недели)

7. ✅ **Виртуальные кабинеты** (4-5 дней)
   - Дерево кабинетов
   - Управление документами в кабинете
   - Навигация по иерархии

---

## 🎯 Рекомендуемый план действий

### Шаг 1: Обновить API клиент
```bash
# Файл: frontend/src/lib/api.ts
# Добавить ~30 новых методов
```

### Шаг 2: Добавить TypeScript типы
```bash
# Файл: frontend/src/types/api.ts
# Добавить интерфейсы для новых сущностей
```

### Шаг 3: Создать UI компоненты
```bash
frontend/src/components/
├── documents/
│   ├── comments/
│   │   ├── DocumentComments.tsx
│   │   ├── CommentItem.tsx
│   │   ├── CommentForm.tsx
│   │   └── CommentThread.tsx
│   ├── versions/
│   │   ├── DocumentVersionHistory.tsx
│   │   ├── DocumentActivityTimeline.tsx
│   │   └── VersionCompareModal.tsx
│   ├── tags/
│   │   ├── TagManager.tsx
│   │   ├── TagSelect.tsx
│   │   └── TagBadge.tsx
│   ├── related/
│   │   ├── RelatedDocumentsList.tsx
│   │   └── AddRelatedDocumentModal.tsx
│   └── cabinets/
│       ├── CabinetBrowser.tsx
│       └── CabinetCard.tsx
```

### Шаг 4: Интеграция в существующие страницы
```bash
# Обновить:
- frontend/src/app/documents/[id]/page.tsx  # Страница документа
- frontend/src/app/documents/page.tsx       # Список документов
- frontend/src/components/documents/DocumentForm.tsx
```

### Шаг 5: Тестирование
- [ ] Unit тесты для API методов
- [ ] Component тесты для UI
- [ ] E2E тесты для основных сценариев
- [ ] Проверка интеграции с уведомлениями

---

## 📝 Примеры интеграции

### Пример 1: Добавление комментариев
```typescript
// В frontend/src/lib/api.ts
async getDocumentComments(documentId: number): Promise<DocumentComment[]> {
    return this.request(`/api/v1/document-comments/?document=${documentId}`);
}

async createDocumentComment(data: CreateCommentData): Promise<DocumentComment> {
    return this.request('/api/v1/document-comments/', {
        method: 'POST',
        body: JSON.stringify(data),
    });
}

async deleteDocumentComment(id: number): Promise<void> {
    return this.request(`/api/v1/document-comments/${id}/`, {
        method: 'DELETE',
    });
}
```

### Пример 2: Работа с тегами
```typescript
// В frontend/src/lib/api.ts
async getDocumentTags(): Promise<DocumentTag[]> {
    return this.request('/api/v1/document-tags/');
}

async createDocumentTag(data: { name: string; color?: string }): Promise<DocumentTag> {
    return this.request('/api/v1/document-tags/', {
        method: 'POST',
        body: JSON.stringify(data),
    });
}
```

### Пример 3: История версий
```typescript
// В frontend/src/lib/api.ts
async getDocumentVersions(id: number): Promise<DocumentVersion[]> {
    return this.request(`/api/v1/documents/${id}/versions/`);
}

async revertDocumentToVersion(id: number, versionId: number): Promise<any> {
    return this.request(`/api/v1/documents/${id}/revert/`, {
        method: 'POST',
        body: JSON.stringify({ version_id: versionId }),
    });
}
```

---

## ⚠️ Важные замечания

### Безопасность
- Все эндпоинты требуют аутентификации (Bearer token)
- Проверка прав доступа осуществляется на бэкенде
- Не забыть обработку ошибок 403 Forbidden

### Производительность
- Использовать React Query для кэширования
- Lazy loading для комментариев (загрузка по требованию)
- Оптимизация миниатюр (кэширование в браузере)
- Pagination для больших списков

### UX/UI
- Skeleton loaders при загрузке
- Оптимистичные обновления UI
- Undo/Redo для критичных операций (удаление, откат версий)
- Toast уведомления об успехе/ошибке

### WebSocket интеграция
- Real-time обновление комментариев
- Уведомления о новых версиях документа
- Уведомления о добавлении в кабинет/связывании

---

## 🔍 Дополнительные возможности

### 1. Расширенный поиск
```typescript
// Добавить фильтры по новым полям
interface DocumentSearchParams {
  search?: string;
  tags?: number[];           // Новое
  type?: number;             // Новое
  cabinet?: number;          // Новое
  has_comments?: boolean;    // Новое
  status?: string;
  folder_id?: number;
  page?: number;
  limit?: number;
}
```

### 2. Bulk операции
```typescript
// Массовые операции
async bulkAddTags(documentIds: number[], tagIds: number[]): Promise<void>
async bulkAddToCabinet(documentIds: number[], cabinetId: number): Promise<void>
```

### 3. Экспорт данных
```typescript
// Экспорт комментариев, истории версий
async exportDocumentHistory(id: number, format: 'pdf' | 'xlsx'): Promise<Blob>
```

---

## 📈 Ожидаемые результаты

После полной интеграции:

✅ **Улучшение UX:**
- Удобное обсуждение документов через комментарии
- Быстрый поиск по тегам и типам
- Визуальный интерфейс для истории версий
- Связывание документов для создания knowledge base

✅ **Повышение продуктивности:**
- Организация документов в виртуальные кабинеты
- Быстрая навигация через связанные документы
- Аудит изменений через версионирование

✅ **Технический долг:**
- 0 недостающих эндпоинтов
- Полная type-safety (TypeScript)
- Покрытие тестами >80%

---

## 🚀 Начало работы

### 1. Создать ветку
```bash
git checkout -b feature/frontend-documents-integration
```

### 2. Установить зависимости (если требуется)
```bash
cd frontend
npm install @tanstack/react-query  # Для кэширования API
npm install date-fns                # Для работы с датами
npm install react-diff-viewer       # Для diff версий (опционально)
```

### 3. Начать с API клиента
```bash
# Редактировать: frontend/src/lib/api.ts
# Добавить методы из раздела "Примеры интеграции"
```

### 4. Добавить типы
```bash
# Редактировать: frontend/src/types/api.ts
# Скопировать интерфейсы из этого документа
```

### 5. Создать первый компонент
```bash
# Начать с комментариев (самый важный функционал)
mkdir -p frontend/src/components/documents/comments
touch frontend/src/components/documents/comments/DocumentComments.tsx
```

---

## 📚 Полезные ссылки

- **Бэкенд API документация:** `backend/docs/guides/NOTIFICATIONS_INTEGRATION.md`
- **Тесты бэкенда:** `backend/tests/api/v1/documents/test_new_features.py`
- **Отчет о тестировании:** `backend/docs/reports/TESTING_NEW_FEATURES_REPORT.md`

---

**Следующие шаги:** Выбрать фичу из Фазы 1 и начать имплементацию!
