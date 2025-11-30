# Улучшения модала создания чатов

## Что добавлено

### 1. Новые типы чатов
- **Чат отдела** (`department`) - автоматически включает всех сотрудников отдела
- **Глобальный чат** (`global`) - для всей компании

### 2. Новые поля

#### Аватар чата
- Загрузка изображения (JPG/PNG/GIF, до 5 МБ)
- Предпросмотр перед загрузкой
- **Автоматическое сжатие** до 512x512px (до 500KB)
- Удаление старых файлов при замене

#### Выбор отдела
- Для типа "Чат отдела"
- Dropdown со всеми отделами
- Автодобавление всех сотрудников отдела

#### Включить всех сотрудников
- Для типов: `announcement`, `global`, `channel`
- Автодобавление всех активных сотрудников компании
- Ограниченная отправка для `channel` и `announcement`

#### Основной чат
- Для типов: `global`, `department`
- Только 1 основной глобальный чат
- Только 1 основной чат на отдел
- Валидация на уровне API

### 3. Улучшенный UI

#### Типы чатов с подсказками
```
Личный: приватный чат с 1 сотрудником
Группа: чат с несколькими участниками
Отдел: автоматически включает всех сотрудников отдела
Канал: для объявлений с ограниченной отправкой
Объявления: односторонняя рассылка
Глобальный: общий чат компании (может быть только 1 основной)
```

#### Динамическое переключение полей
- **Private**: только выбор участника
- **Group**: название + описание + аватар + участники
- **Department**: название + описание + аватар + отдел + "основной"
- **Global**: название + описание + аватар + "включить всех" + "основной"
- **Channel/Announcement**: название + описание + аватар + "включить всех"

### 4. API изменения

#### FormData support
```javascript
// Теперь поддерживает загрузку файлов
const formData = new FormData();
formData.append('type', 'group');
formData.append('name', 'Команда разработки');
formData.append('avatar', file);
formData.append('participant_ids', [1, 2, 3]);
```

#### Новые параметры API
- `avatar` (file) - файл аватара
- `department_id` (int) - ID отдела для `type=department`
- `include_all_employees` (bool) - включить всех сотрудников
- `is_main` (bool) - сделать основным чатом

#### Валидация
- ✅ Проверка типа чата
- ✅ Обязательное название (кроме private)
- ✅ Обязательный отдел для `department`
- ✅ Уникальность основного глобального чата
- ✅ Уникальность основного чата отдела

### 5. Автоматическое сжатие аватаров

#### Signal `compress_and_cleanup_chat_avatar`
```python
@receiver(pre_save, sender='communications.Chat')
def compress_and_cleanup_chat_avatar(sender, instance, **kwargs):
    # 1. Сжимает новый аватар до 512x512px (макс 500KB)
    # 2. Удаляет старый файл при замене
    # 3. Использует LANCZOS для высокого качества
```

#### Параметры сжатия
- Размер: 512x512px (оптимально для отображения)
- Формат: JPEG (универсальный)
- Качество: 50-85 (бинарный поиск оптимального)
- Максимум: 500KB

### 6. Автодобавление участников

#### Для `include_all_employees=True`
```python
# Добавляются все активные сотрудники
all_employees = Employee.objects.filter(is_active=True)

# Права зависят от типа чата:
# - channel/announcement: can_send_messages=False
# - остальные: can_send_messages=True
```

#### Для `type=department`
```python
# Добавляются сотрудники отдела
dept_employees = EmployeeDepartment.objects.filter(
    department=department,
    is_active=True
)

# Все получают can_send_messages=True
```

## Примеры использования

### Создать групповой чат с аватаром
```javascript
const formData = new FormData();
formData.append('type', 'group');
formData.append('name', 'DevOps Team');
formData.append('description', 'Обсуждение инфраструктуры');
formData.append('avatar', avatarFile);
formData.append('participant_ids', 5);
formData.append('participant_ids', 12);
formData.append('participant_ids', 23);

fetch('/communications/api/chat/create/', {
  method: 'POST',
  headers: { 'X-CSRFToken': csrftoken },
  body: formData
});
```

### Создать основной чат отдела
```javascript
const formData = new FormData();
formData.append('type', 'department');
formData.append('name', 'Отдел разработки');
formData.append('department_id', 3);
formData.append('is_main', 'true');

fetch('/communications/api/chat/create/', {
  method: 'POST',
  headers: { 'X-CSRFToken': csrftoken },
  body: formData
});
```

### Создать канал с аватаром для всех
```javascript
const formData = new FormData();
formData.append('type', 'channel');
formData.append('name', 'Новости компании');
formData.append('description', 'Официальные объявления');
formData.append('avatar', avatarFile);
formData.append('include_all_employees', 'true');

fetch('/communications/api/chat/create/', {
  method: 'POST',
  headers: { 'X-CSRFToken': csrftoken },
  body: formData
});
```

## Технические детали

### Структура модели Chat
```python
class Chat(models.Model):
    type = CharField(choices=[...])
    name = CharField(max_length=255)
    description = TextField()
    avatar = ImageField(upload_to='chat_avatars/%Y/%m/')  # NEW
    created_by = ForeignKey(Employee)
    department = ForeignKey(Department)                   # NEW
    include_all_employees = BooleanField(default=False)   # NEW
    is_main = BooleanField(default=False)                 # NEW
    participants = ManyToManyField(Employee)
    created_at = DateTimeField(auto_now_add=True)
```

### Constraints
```python
# Только 1 основной глобальный чат
UniqueConstraint(
    fields=["type"],
    condition=Q(is_main=True, type="global"),
    name="unique_main_global_chat"
)

# Только 1 основной чат на отдел
UniqueConstraint(
    fields=["type", "department"],
    condition=Q(is_main=True, type="department"),
    name="unique_main_department_chat"
)
```

### Путь хранения аватаров
```
media/
  chat_avatars/
    2024/
      11/
        chat_avatar_abc123.jpg  (сжато до 512x512, <500KB)
```

## Совместимость

### Backward compatibility
- ✅ Старые чаты без аватаров работают как прежде
- ✅ API поддерживает JSON (legacy) и FormData (новый)
- ✅ Все новые поля опциональные (кроме валидируемых случаев)

### Frontend
- Модал: Bootstrap 5
- Preview: FileReader API
- Validation: Client-side + Server-side
- CSRF: Из cookie или hidden input

## Производительность

### Оптимизации
- ✅ Сжатие аватаров на лету (JPEG quality 50-85)
- ✅ Удаление старых файлов (нет дубликатов)
- ✅ Batch добавление участников (без N+1 queries)
- ✅ `select_related('employee')` для отделов

### Размеры файлов
- **До**: 8.3 MB PNG, 800+ KB JPEG
- **После**: <500 KB JPEG, 512x512px
- **Экономия**: ~90-95% места на диске

## Тестирование

### Проверить создание чатов
1. Личный чат с 1 участником ✅
2. Групповой чат с аватаром ✅
3. Чат отдела с автодобавлением ✅
4. Глобальный основной чат (только 1) ✅
5. Канал для всех с ограниченной отправкой ✅

### Проверить сжатие
1. Загрузить PNG 5MB → сжато до <500KB JPEG ✅
2. Заменить аватар → старый файл удален ✅
3. Проверить preview в модале ✅

### Проверить валидацию
1. Попытка создать 2 основных глобальных чата → ошибка ✅
2. Чат отдела без выбора отдела → ошибка ✅
3. Файл >5MB → отклонен на клиенте ✅

## Changelog

### v1.0 (30 ноября 2024)
- ✅ Добавлены поля: avatar, department, include_all_employees, is_main
- ✅ Реализовано автосжатие аватаров (512x512, <500KB)
- ✅ Добавлены типы: department, global
- ✅ Динамические поля в модале
- ✅ API поддержка FormData + файлов
- ✅ Валидация основных чатов
- ✅ Автодобавление участников по правилам
- ✅ Signal для сжатия и cleanup

## TODO

- [ ] Crop аватара перед загрузкой (client-side)
- [ ] Batch upload нескольких аватаров
- [ ] История изменений аватара чата
- [ ] Права на изменение аватара (только owner/admin)
- [ ] Предпросмотр аватара в списке чатов
- [ ] Поиск чатов по названию в модале
