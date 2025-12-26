# Backend Scripts

Вспомогательные скрипты для разработки, тестирования и диагностики.

## 📁 Структура

### [manual_tests/](manual_tests/)
**22 скрипта** - Ручные тесты для быстрой проверки функционала

Запуск из корня backend:
```bash
.venv/Scripts/python scripts/manual_tests/test_ldap_simple.py
```

### [diagnostic/](diagnostic/)
**8 скриптов** - Диагностика и проверка состояния системы

```bash
.venv/Scripts/python scripts/diagnostic/check_ldap_user.py
.venv/Scripts/python scripts/diagnostic/check_chat_access.py
```

### [utils/](utils/)
**6 утилит** - Генерация тестовых данных и анализ

```bash
.venv/Scripts/python scripts/utils/create_test_data.py
.venv/Scripts/python scripts/utils/generate_notification.py
```

### [ldap/](ldap/)
**Shell скрипты** - Тестирование LDAP сервера

```bash
bash scripts/ldap/ldap-test.sh
```

## 🎯 Использование

### Важно!
Всегда используйте виртуальное окружение при запуске скриптов:
```bash
# Полный путь к Python
.venv/Scripts/python scripts/manual_tests/test_*.py

# Или активируйте venv
source .venv/Scripts/activate  # Linux/Mac
.venv\Scripts\activate         # Windows
python scripts/manual_tests/test_*.py
```

### Django management команды
Для доступа к Django ORM в скриптах используйте:
```python
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'eusrr_backend.settings')
django.setup()
```

## 📝 Рекомендации

1. **Именование**: Используйте понятные префиксы
   - `test_*` - тестовые скрипты
   - `check_*` - проверки
   - `create_*` - генераторы
   - `analyze_*` - анализ

2. **Документация**: Добавляйте docstring в начало каждого скрипта

3. **Аргументы**: Используйте argparse для параметров

4. **Очистка**: Удаляйте устаревшие скрипты после интеграции в тесты

## 🔗 См. также

- [backend/tests/](../tests/) - Официальные unit/integration тесты  
- [backend/docs/testing/](../docs/testing/) - Документация по тестированию
