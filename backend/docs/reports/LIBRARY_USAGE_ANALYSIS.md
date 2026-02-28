# Анализ использования библиотек для документооборота

**Дата:** 28 февраля 2026 г.  
**Статус:** Анализ установленных библиотек и степени использования их возможностей

---

## 📊 Общая статистика

| Библиотека | Версия | Использование | Комментарий |
|------------|--------|---------------|-------------|
| **django-filer** | 3.4.4 | ~25% | Базовые возможности файлового хранения |
| **django-reversion** | 6.1.0 | ~15% | Только регистрация моделей, нет API |
| **django-fsm** | 3.0.1 | ~80% | Полный workflow с 7 transitions |
| **easy-thumbnails** | 2.10.1 | ~40% | Настройки есть, активное использование не проверено |
| **django-mptt** | 0.18.0 | ~60% | Используется через filer для иерархии папок |

**Средний процент использования: ~44%**

---

## 1. django-filer 3.4.4 (~25% использования)

### ✅ Что используется:

#### Базовые возможности:
- ✅ `FilerFileField` - поле для файлов
- ✅ `Folder` модель - иерархическая структура папок
- ✅ `File` модель - хранение файлов через django-filer
- ✅ Связь Document → filer.File
- ✅ Связь Document → filer.Folder
- ✅ ACL настройки (`FILER_ENABLE_PERMISSIONS = True`)
- ✅ Приватные файлы по умолчанию (`FILER_IS_PUBLIC_DEFAULT = False`)

#### API:
- ✅ `FolderViewSet` - CRUD для папок
- ✅ `FolderViewSet.children()` - получение дочерних папок
- ✅ `FolderViewSet.documents()` - документы в папке
- ✅ Фильтр по `?parent_id=` и `?root=true`

### ❌ Что НЕ используется:

#### Продвинутые возможности:
- ❌ **FilerImageField** - специальное поле для изображений с метаданными (EXIF, геотеги)
- ❌ **ThumbnailOption** - кастомные пресеты миниатюр (настройки есть, но не используются в коде)
- ❌ **ClipboardItem** - буфер обмена для администратора
- ❌ **canonical_url** - прямые URL к файлам (настройка есть: `FILER_CANONICAL_URL = 'canonical/'`)
- ❌ **icons_url** - URL к иконкам типов файлов
- ❌ **subject_location** - точка фокуса для умной обрезки изображений
- ❌ **is_public / file_ptr** - управление публичностью отдельных файлов

#### Миниатюры:
- ❌ Генерация thumbnails для PDF (библиотека поддерживает через pdf2image)
- ❌ Кэширование thumbnails
- ❌ Watermarks на изображениях
- ❌ EXIF-метаданные для фото

#### Permissions:
- ❌ **FilerPermissions** - детальные права на файлы и папки
- ❌ Группы доступа к папкам
- ❌ Наследование прав в иерархии папок

#### Admin Features:
- ❌ Drag & Drop интерфейс администратора
- ❌ Clipboard для копирования/перемещения файлов
- ❌ Массовые операции над файлами
- ❌ Directory listing views

#### Интеграция:
- ❌ `django-polymorphic` для типов файлов (установлено, но минимально используется)
- ❌ REST API от django-filer (мы используем свой собственный)

### 💡 Рекомендации:

**Высокий приоритет:**
1. **Thumbnails API** - добавить endpoint для получения миниатюр разных размеров
2. **Subject location** - для умной обрезки аватаров и превью
3. **Детальные permissions** - права на уровне папок и файлов

**Средний приоритет:**
4. **FilerImageField** - для работы с изображениями (метаданные, EXIF)
5. **Canonical URLs** - прямые ссылки на файлы без перенаправлений
6. **Clipboard** - буфер обмена в админке для удобства

**Низкий приоритет:**
7. **Watermarks** - водяные знаки на документы
8. **PDF thumbnails** - превью PDF через pdf2image

---

## 2. django-reversion 6.1.0 (~15% использования)

### ✅ Что используется:

- ✅ `@reversion.register()` на модели `Document` и `DocumentAcknowledgement`
- ✅ Автоматическое сохранение версий при изменениях
- ✅ Настройка в `INSTALLED_APPS`

### ❌ Что НЕ используется:

#### API для версий:
- ❌ **Version.objects.get_for_object()** - получение истории версий
- ❌ **Version.revision** - доступ к ревизиям
- ❌ **Version.field_dict** - сравнение версий
- ❌ **get_deleted()** - восстановление удаленных объектов

#### Endpoints (полностью отсутствуют):
- ❌ `GET /api/v1/documents/{id}/versions/` - список версий
- ❌ `GET /api/v1/documents/{id}/versions/{version_id}/` - конкретная версия
- ❌ `POST /api/v1/documents/{id}/revert/` - откат к версии
- ❌ `GET /api/v1/documents/{id}/activity/` - timeline активности
- ❌ `GET /api/v1/documents/{id}/compare/` - сравнение версий

#### Продвинутые возможности:
- ❌ **RevisionMiddleware** - автоматическое связывание версий с пользователем (middleware не добавлен!)
- ❌ **Комментарии к версиям** - `reversion.create_revision(comment=...)`
- ❌ **Метаданные версий** - хранение дополнительной информации
- ❌ **Batch revisions** - группировка изменений в одну ревизию
- ❌ **Version filtering** - фильтрация версий по пользователю/дате

#### Admin:
- ❌ **VersionAdmin** - интерфейс истории в админке
- ❌ Кнопка "Revert" для отката
- ❌ Diff между версиями

### 💡 Рекомендации:

**КРИТИЧНО (блокирует фронтенд):**
1. ✅ Добавить `RevisionMiddleware` в `MIDDLEWARE`
2. ✅ Реализовать endpoint `/versions/` - список версий документа
3. ✅ Реализовать endpoint `/activity/` - timeline для вкладки Activity
4. ✅ Реализовать endpoint `/revert/` - откат к версии

**Высокий приоритет:**
5. Метаданные к версиям (кто, когда, что изменил)
6. Комментарии к изменениям
7. Сравнение версий (diff)

**Средний приоритет:**
8. VersionAdmin в админке
9. Восстановление удаленных документов
10. Фильтрация версий

---

## 3. django-fsm 3.0.1 (~80% использования)

### ✅ Что используется:

#### Модель:
- ✅ `FSMField` с 6 статусами (draft, in_review, approved, published, archived, rejected)
- ✅ `@transition` декораторы для 7 transitions
- ✅ `protected=True` - защита от прямого изменения status

#### Transitions:
- ✅ `submit_for_review()` - draft → in_review
- ✅ `approve()` - in_review → approved
- ✅ `reject()` - in_review → rejected
- ✅ `publish()` - approved → published
- ✅ `return_to_draft()` - in_review/draft → draft
- ✅ `archive()` - published → archived
- ✅ `unarchive()` - archived → published

#### API:
- ✅ Все 7 transitions имеют endpoint `POST /documents/{id}/{action}/`
- ✅ Автоматическое сохранение через `.save()` после transition

#### Admin:
- ✅ `get_available_FIELD_transitions()` - доступные переходы

### ❌ Что НЕ используется:

#### Продвинутые transitions:
- ❌ **Conditions** - условия выполнения перехода (`@transition(..., conditions=[...])`)
- ❌ **Permissions** - права на переход (`permission='documents.can_approve'`)
- ❌ **Custom targets** - динамические целевые статусы
- ❌ **on_error** - обработка ошибок transition

#### Hooks и сигналы:
- ❌ **pre_transition** - действия перед переходом
- ❌ **post_transition** - действия после перехода (сейчас используются сигналы Django, можно было бы FSM)
- ❌ **Transition history** - автоматическая история переходов

#### Интеграция:
- ❌ **django-fsm-log** - детальное логирование переходов (не установлено)
- ❌ **FSMAdmin** - улучшенный интерфейс админки с кнопками переходов

#### Graphviz:
- ❌ **get_graph()** - визуализация state machine
- ❌ Диаграмма workflow для документации

### 💡 Рекомендации:

**Высокий приоритет:**
1. **Conditions** - проверять права перед transition (например, `can_approve`)
2. **Permissions** - интеграция с django permissions
3. **django-fsm-log** - установить и логировать все переходы

**Средний приоритет:**
4. **pre_transition/post_transition** - заменить текущие сигналы на FSM hooks
5. **on_error** - обработка ошибок (например, если документ без файла)
6. **FSMAdmin** - улучшить админку

**Низкий приоритет:**
7. **Graph visualization** - диаграмма workflow для документации
8. **Custom targets** - если потребуются сложные workflows

---

## 4. easy-thumbnails 2.10.1 (~40% использования)

### ✅ Что используется (в settings.py):

#### Настройки:
- ✅ `THUMBNAIL_PROCESSORS` - процессоры обработки
- ✅ `colorspace` - конвертация цветового пространства
- ✅ `autocrop` - автообрезка
- ✅ `scale_and_crop_with_subject_location` - умная обрезка (filer)
- ✅ `filters` - фильтры изображений
- ✅ `THUMBNAIL_HIGH_RESOLUTION = True` - Retina поддержка
- ✅ `THUMBNAIL_PRESERVE_EXTENSIONS` - сохранение PNG/GIF

#### Размеры (в settings):
```python
THUMBNAIL_ALIASES = {
    '': {
        'admin_thumbnail': {'size': (60, 60), 'crop': True},
        'file_card': {'size': (200, 150), 'crop': True},
        'preview': {'size': (800, 600), 'crop': False},
    }
}
```

### ❌ Что НЕ используется:

#### В коде:
- ❌ **get_thumbnailer()** - генерация thumbnails в коде
- ❌ **{% thumbnail %}** template tag - использование в шаблонах (у нас React фронтенд)
- ❌ API endpoints для получения thumbnails разных размеров
- ❌ **ThumbnailerNamespace** - кастомные namespace для разных разрешений

#### Продвинутые процессоры:
- ❌ **background** - фоновый цвет для прозрачных
- ❌ **detail** - резкость изображения
- ❌ **replace_alpha** - замена прозрачности
- ❌ **sharpen** - усиление резкости

#### Опции:
- ❌ **quality** - качество JPEG
- ❌ **subsampling** - субдискретизация для размера файла
- ❌ **progressive** - прогрессивная загрузка JPEG
- ❌ **orientation** - автоповорот по EXIF

#### Кэширование:
- ❌ Настройки кэширования thumbnails
- ❌ Warming cache (предгенерация)
- ❌ Очистка устаревших thumbnails

### 💡 Рекомендации:

**Высокий приоритет:**
1. **API для thumbnails** - `GET /documents/{id}/thumbnail/?size=preview`
2. **Предгенерация** - создавать thumbnails при загрузке
3. **Quality settings** - настроить качество для баланса размер/качество

**Средний приоритет:**
4. **Progressive JPEG** - для быстрой загрузки
5. **Warming** - предгенерация популярных размеров
6. **Orientation** - автоповорот фото

---

## 5. django-mptt 0.18.0 (~60% использования)

### ✅ Что используется:

- ✅ Используется через django-filer для `filer.Folder` (иерархия папок)
- ✅ Queries через MPTT для получения `children` и `parent`
- ✅ Настройка в `INSTALLED_APPS`

### ❌ Что НЕ используется:

#### В собственных моделях:
- ❌ **MPTTModel** - не используем для своих моделей (например, Cabinet)
- ❌ **TreeForeignKey** - только через filer
- ❌ **get_descendants()** - получение всех потомков
- ❌ **get_ancestors()** - получение всех предков
- ❌ **get_root()** - корневой элемент

#### Template tags:
- ❌ **{% recursetree %}** - рекурсивный вывод дерева (React фронтенд)
- ❌ **{% full_tree_for_model %}** - полное дерево

#### Manager методы:
- ❌ **add_related_count()** - подсчет связанных объектов
- ❌ **move_to()** - перемещение узлов
- ❌ **insert_at()** - вставка в дерево

#### Admin:
- ❌ **MPTTModelAdmin** - drag & drop в админке
- ❌ **TreeRelatedFieldListFilter** - фильтр по дереву

### 💡 Рекомендации:

**Средний приоритет:**
1. **Использовать MPTTModel** для Cabinet (у него есть parent, но не MPTT)
2. **get_descendants()** - для получения всех подпапок с документами
3. **MPTTModelAdmin** - улучшить админку папок

---

## 📈 Сводная таблица неиспользуемых возможностей

### Критичные (блокируют фронтенд):
1. ✅ **django-reversion API** - endpoints для версий и activity (вкладки в modal)
2. ✅ **RevisionMiddleware** - связывание версий с пользователем

### Высокий приоритет:
3. **Thumbnails API** - endpoint для получения превью разных размеров
4. **django-filer permissions** - детальные права на папки/файлы
5. **django-fsm conditions** - условия и права для transitions
6. **Metadata к версиям** - кто, когда, что изменил

### Средний приоритет:
7. **FilerImageField** - для изображений с метаданными
8. **Subject location** - умная обрезка изображений
9. **Django-fsm-log** - детальное логирование transitions
10. **Cabinet с MPTT** - иерархические виртуальные хранилища

### Низкий приоритет:
11. Clipboard в админке
12. Watermarks
13. Graph visualization для FSM
14. Восстановление удаленных документов

---

## 🎯 Рекомендуемый план действий

### Этап 1: Критичные задачи (разблокировать фронтенд)
**Срок: 1-2 дня**

```python
# 1. Добавить RevisionMiddleware
MIDDLEWARE = [
    ...
    'reversion.middleware.RevisionMiddleware',  # ← Добавить
    ...
]

# 2. Реализовать ViewSet actions:
@action(detail=True, methods=['get'])
def versions(self, request, pk=None):
    """История версий документа"""
    
@action(detail=True, methods=['get'])
def activity(self, request, pk=None):
    """Timeline активности (версии + аудит)"""
    
@action(detail=True, methods=['post'])
def revert(self, request, pk=None):
    """Откат к версии"""
```

### Этап 2: Высокий приоритет (улучшить UX)
**Срок: 3-5 дней**

```python
# 3. Thumbnails API
@action(detail=True, methods=['get'])
def thumbnail(self, request, pk=None):
    """Получить thumbnail документа
    
    Query params:
        size: admin_thumbnail | file_card | preview
    """
    
# 4. Условия и права для FSM
@transition(
    field=status,
    source='in_review',
    target='approved',
    permission='documents.can_approve',
    conditions=[has_required_fields, user_has_permission]
)
def approve(self):
    """Одобрить документ"""
```

### Этап 3: Средний приоритет (продвинутые фичи)
**Срок: 1 неделя**

```python
# 5. Установить django-fsm-log
pip install django-fsm-log

# 6. FilerImageField для изображений
class Document(models.Model):
    file = FilerFileField(...)  # Для общих файлов
    image = FilerImageField(...)  # Для изображений (nullable)
    
# 7. Permissions на папки
class FolderViewSet:
    def check_folder_permission(self, user, folder, action):
        """Проверить права на папку"""
```

---

## 📊 Итоговая оценка

| Критерий | Оценка | Комментарий |
|----------|--------|-------------|
| Базовые возможности | ✅ 85% | CRUD, workflow, папки работают |
| Продвинутые возможности | ⚠️ 30% | Версии, thumbnails, permissions не используются |
| Frontend интеграция | ⚠️ 60% | API есть, но нет endpoints для versions/thumbnails |
| Admin интеграция | ⚠️ 40% | Базовый функционал, нет drag&drop, clipboard |
| Performance | ⚠️ 50% | Нет кэширования thumbnails, нет предгенерации |

**Общая оценка использования библиотек: 44%**

---

## 🔍 Дополнительные библиотеки (не установлены)

Библиотеки, которые могли бы улучшить документооборот:

1. **django-fsm-log** - логирование FSM transitions
2. **django-admin-sortable2** - drag & drop в админке
3. **pdf2image** - thumbnails для PDF
4. **python-magic** - определение MIME-типов
5. **OCRmyPDF** - OCR для сканов
6. **WeasyPrint** - генерация PDF из HTML

---

**Подготовил:** GitHub Copilot  
**Дата:** 28 февраля 2026 г.
