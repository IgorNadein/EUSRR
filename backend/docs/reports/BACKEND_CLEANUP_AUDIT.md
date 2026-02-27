# Аудит папки backend/

**Дата:** 26 декабря 2025 г.  
**Задача:** Очистка главной папки Django приложения

---

## 🔍 Найдено лишних файлов

### 📊 Статистика

| Тип файлов | Количество | Категория |
|------------|------------|-----------|
| test_*.py | 22 файла | Тестовые скрипты |
| check_*.py | 5 файлов | Диагностические проверки |
| *_test*.py и утилиты | 7 файлов | Вспомогательные скрипты |
| *.md | 12 файлов | Техническая документация |
| *.sh | 1 файл | Shell скрипты |
| ldap_test_* | 2 папки | Тестовые данные LDAP |
| **ИТОГО** | **49 файлов/папок** | Требуют реорганизации |

---

## 📂 Детальный список

### 1. Тестовые скрипты (22 файла)

**test_*.py** - ручные тесты для быстрой проверки:
```
test_all_signals.py              # Тестирование сигналов
test_announcement_notifications.py # Уведомления объявлений
test_avatar_simple.py            # Простой тест аватаров
test_corporate_ip.py             # Корпоративные IP
test_create_announcement_message.py # Создание объявлений
test_email.py                    # Email функционал
test_ip_restrictions.py          # IP ограничения
test_ip_simple.py                # Простой тест IP
test_ldap_simple.py              # Простой тест LDAP
test_message_serialization.py   # Сериализация сообщений
test_notification_create.py     # Создание уведомлений
test_notification_debug.py      # Отладка уведомлений
test_notification_signals.py    # Сигналы уведомлений
test_pagination.py               # Пагинация
test_phone_export.py             # Экспорт телефонов
test_reactions_api.py            # API реакций
test_recipients.py               # Получатели
test_recipients_api.py           # API получателей
test_register_api.py             # API регистрации
test_reply_update.py             # Обновление ответов
test_requests_access.py          # Доступ к заявкам
test_requests_access_detailed.py # Детальный доступ к заявкам
```

**Рекомендация:** Переместить в `backend/scripts/manual_tests/`

---

### 2. Диагностические скрипты (5 файлов)

**check_*.py** - проверка состояния системы:
```
check_chat_access.py      # Проверка доступа к чатам
check_ldap_user.py        # Проверка пользователя LDAP
check_pagination.py       # Проверка пагинации
check_reactions.py        # Проверка реакций
check_templates.py        # Проверка шаблонов
```

**Рекомендация:** Переместить в `backend/scripts/diagnostic/`

---

### 3. Вспомогательные скрипты (8 файлов)

**Утилиты и генераторы:**
```
analyze_templates.py      # Анализ шаблонов
create_test_data.py       # Создание тестовых данных
diagnose_page.py          # Диагностика страниц
diagnostic_summary.py     # Сводка диагностики
generate_notification.py  # Генерация уведомлений
quick_test.py             # Быстрые тесты
render_test_page.py       # Рендеринг тестовых страниц
simple_create_users.py    # Простое создание пользователей
```

**Рекомендация:** 
- Утилиты → `backend/scripts/utils/`
- Диагностика → `backend/scripts/diagnostic/`

---

### 4. MD документация (12 файлов)

**Техническая документация в корне backend/:**
```
API_ANALYSIS.md                  # Анализ API
API_REFACTORING_SUMMARY.md       # Рефакторинг API
CONTEXT_MENU_DEBUG.md            # Отладка контекстного меню
CONTEXT_MENU_GUIDE.md            # Руководство контекстного меню
MESSAGE_DELETE_DEBUG.md          # Отладка удаления сообщений
MESSAGE_DELETE_FIX.md            # Исправление удаления
POSITION_PERMISSIONS_TESTING.md  # Тестирование прав должностей
REACTIONS_GUIDE.md               # Руководство по реакциям
REACTIONS_IMPLEMENTATION.md      # Реализация реакций
REQUESTS_API_TESTING_PLAN.md     # План тестирования API заявок
TEST_IMAGE_SCRIPTS.md            # Скрипты тестирования изображений
VIEWSET_ANALYSIS.md              # Анализ ViewSet
```

**Рекомендация:**
- GUIDE → переместить в `backend/docs/guides/`
- DEBUG/FIX → переместить в `backend/docs/troubleshooting/`
- ANALYSIS → переместить в `backend/docs/architecture/`
- TESTING → переместить в `backend/docs/testing/`

---

### 5. Shell скрипты (1 файл)

```
ldap-test.sh  # Тестирование LDAP сервера
```

**Рекомендация:** Переместить в `backend/scripts/ldap/`

---

### 6. Тестовые данные LDAP (2 папки)

```
ldap_test_config/  # Конфигурация тестового LDAP
ldap_test_data/    # Данные тестового LDAP
```

**Содержимое:**
- `ldap_test_config/` - конфигурационные файлы OpenLDAP
- `ldap_test_data/` - файлы базы данных (data.mdb, lock.mdb)

**Рекомендация:** 
- Если используются → переместить в `backend/tests/fixtures/ldap/`
- Если не используются → можно удалить (данные автоматически генерируются)

---

## 🗂️ Предлагаемая структура

```
backend/
├── manage.py                    # Основной файл Django
├── scripts/                     # Вспомогательные скрипты
│   ├── manual_tests/           # test_*.py (22 файла)
│   ├── diagnostic/             # check_*.py (5 файлов)
│   ├── utils/                  # create_*, generate_* (утилиты)
│   └── ldap/                   # ldap-test.sh
├── docs/                       # Документация backend
│   ├── guides/                 # *_GUIDE.md
│   ├── troubleshooting/        # *_DEBUG.md, *_FIX.md
│   ├── architecture/           # *_ANALYSIS.md
│   └── testing/                # *_TESTING*.md
├── tests/                      # Официальные тесты
│   └── fixtures/
│       └── ldap/               # ldap_test_config/, ldap_test_data/
└── [Django apps...]            # api/, employees/, etc.
```

---

## ✅ План действий

### Шаг 1: Создать структуру папок
```bash
mkdir -p backend/scripts/{manual_tests,diagnostic,utils,ldap}
mkdir -p backend/docs/{guides,troubleshooting,architecture,testing}
```

### Шаг 2: Переместить тестовые скрипты (22)
```bash
mv backend/test_*.py backend/scripts/manual_tests/
```

### Шаг 3: Переместить диагностические скрипты (5)
```bash
mv backend/check_*.py backend/scripts/diagnostic/
mv backend/diagnostic_summary.py backend/scripts/diagnostic/
mv backend/diagnose_page.py backend/scripts/diagnostic/
```

### Шаг 4: Переместить утилиты (5)
```bash
mv backend/analyze_templates.py backend/scripts/utils/
mv backend/create_test_data.py backend/scripts/utils/
mv backend/generate_notification.py backend/scripts/utils/
mv backend/quick_test.py backend/scripts/utils/
mv backend/render_test_page.py backend/scripts/utils/
mv backend/simple_create_users.py backend/scripts/utils/
```

### Шаг 5: Переместить shell скрипты (1)
```bash
mv backend/ldap-test.sh backend/scripts/ldap/
```

### Шаг 6: Реорганизовать MD файлы (12)

**Guides (2):**
```bash
mv backend/CONTEXT_MENU_GUIDE.md backend/docs/guides/
mv backend/REACTIONS_GUIDE.md backend/docs/guides/
```

**Troubleshooting (2):**
```bash
mv backend/CONTEXT_MENU_DEBUG.md backend/docs/troubleshooting/
mv backend/MESSAGE_DELETE_DEBUG.md backend/docs/troubleshooting/
mv backend/MESSAGE_DELETE_FIX.md backend/docs/troubleshooting/
```

**Architecture (3):**
```bash
mv backend/API_ANALYSIS.md backend/docs/architecture/
mv backend/VIEWSET_ANALYSIS.md backend/docs/architecture/
mv backend/API_REFACTORING_SUMMARY.md backend/docs/architecture/
```

**Testing (3):**
```bash
mv backend/POSITION_PERMISSIONS_TESTING.md backend/docs/testing/
mv backend/REQUESTS_API_TESTING_PLAN.md backend/docs/testing/
mv backend/TEST_IMAGE_SCRIPTS.md backend/docs/testing/
```

**Completed (2):**
```bash
mv backend/REACTIONS_IMPLEMENTATION.md backend/docs/completed/
```

### Шаг 7: LDAP тестовые данные
**Опция 1 (если используются):**
```bash
mkdir -p backend/tests/fixtures/ldap/
mv backend/ldap_test_config backend/tests/fixtures/ldap/
mv backend/ldap_test_data backend/tests/fixtures/ldap/
```

**Опция 2 (если не используются):**
```bash
rm -rf backend/ldap_test_config backend/ldap_test_data
```

### Шаг 8: Создать README файлы
- `backend/scripts/README.md` - описание всех скриптов
- `backend/docs/README.md` - структура документации

---

## 📊 Результат

### До очистки:
```
backend/
├── manage.py
├── test_*.py (22 файла)
├── check_*.py (5 файлов)
├── analyze_*.py и др. (8 файлов)
├── *.md (12 файлов)
├── ldap-test.sh
├── ldap_test_config/
├── ldap_test_data/
└── [Django apps...]
```
**ИТОГО в корне:** 49 лишних файлов/папок

### После очистки:
```
backend/
├── manage.py
├── scripts/           # Все скрипты организованы
├── docs/              # Вся документация организована
├── tests/fixtures/    # Тестовые данные
└── [Django apps...]   # Только Django приложения
```
**В корне:** Только manage.py и Django приложения ✨

---

## 💡 Дополнительные рекомендации

### 1. Добавить .gitignore правила
```gitignore
# LDAP test data (автогенерируется)
backend/tests/fixtures/ldap/ldap_test_data/
```

### 2. Документировать скрипты
В каждом README.md описать:
- Назначение скриптов
- Как запускать
- Когда использовать
- Примеры использования

### 3. Очистить неиспользуемые скрипты
После перемещения проверить:
- Какие скрипты устарели
- Какие дублируют функционал тестов
- Что можно удалить

---

## 🎯 Приоритет выполнения

1. ✅ **Высокий** - Переместить test_* скрипты (захламляют корень)
2. ✅ **Высокий** - Переместить check_* скрипты
3. ✅ **Средний** - Реорганизовать MD документацию
4. ✅ **Средний** - Переместить утилиты
5. ⚠️ **Низкий** - Решить судьбу ldap_test_* папок

---

**Готов приступить к выполнению?** Начнем с создания структуры и перемещения файлов.
