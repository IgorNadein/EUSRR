# Контрольный список качества кода (Code Quality Checklist)

## Обнаруженные проблемы и решения

### 1. 🔴 Критично: Небезопасный доступ к `request.data`

**Проблема:**
```python
value = request.data['key']  # ❌ KeyError если ключа нет
```

**Решение:**
```python
value = request.data.get('key')  # ✅ Вернёт None
value = request.data.get('key', default)  # ✅ С дефолтом
```

**Найдено в:**
- `notifications/api/views.py` (8 мест)
- `common/ldap_password_mixin.py` (1 место)

---

### 2. 🟡 Важно: QueryDict vs dict несовместимость

**Проблема:**
```python
# DRF request.data может быть dict (JSON) или QueryDict (form data)
data = request.data.dict()  # ❌ dict не имеет метода .dict()
```

**Решение:**
```python
data = request.data
result = data.dict() if hasattr(data, 'dict') else dict(data)  # ✅
```

**Статус:** ✅ Исправлено в `api/v1/employees/views/employees.py`

---

### 3. 🟡 Важно: Небезопасный `int()` без обработки

**Проблема:**
```python
page = int(request.GET.get('page', 1))  # ❌ ValueError если 'abc'
```

**Решение:**
```python
# Вариант 1: try/except
try:
    page = int(request.GET.get('page', 1))
except (ValueError, TypeError):
    page = 1

# Вариант 2: Helper функция
def safe_int(value, default=0):
    try:
        return int(value)
    except (ValueError, TypeError):
        return default

page = safe_int(request.GET.get('page'), 1)
```

**Найдено в:**
- `communications/api/viewsets.py` (4 места)
- `notifications/api/views.py` (2 места)
- `api/v1/search/views.py` (1 место)
- `api/v1/procurement/views.py` (1 место)

---

### 4. 🟢 Средне: `.strip()` без проверки на None

**Проблема:**
```python
text = some_value.strip()  # ❌ AttributeError если None
```

**Решение:**
```python
text = (some_value or '').strip()  # ✅
text = str(some_value).strip() if some_value else ''  # ✅
```

---

## Автоматизация проверки

### Скрипт для аудита

Запуск:
```bash
./scripts/audit_code_patterns.sh
```

### Pre-commit hooks

Добавить в `.pre-commit-config.yaml`:
```yaml
repos:
  - repo: local
    hooks:
      - id: check-unsafe-data-access
        name: Check unsafe request.data access
        entry: bash -c 'grep -rn "request\.data\[" --include="*.py" . | grep -v "# noqa" && exit 1 || exit 0'
        language: system
        pass_filenames: false
```

### Линтеры

**Flake8** с плагинами:
```bash
pip install flake8 flake8-bugbear flake8-comprehensions
flake8 --max-line-length=100 --extend-ignore=E203,W503
```

**Pylint**:
```bash
pip install pylint
pylint --disable=C0111,C0103 employees/
```

**MyPy** (статическая типизация):
```bash
pip install mypy django-stubs djangorestframework-stubs
mypy --config-file=mypy.ini employees/
```

---

## Тесты для обнаружения проблем

### Unit-тесты для API

```python
from rest_framework.test import APITestCase

class EmployeeAPITestCase(APITestCase):
    def test_patch_with_json(self):
        """Тест PATCH с JSON payload"""
        response = self.client.patch(
            '/api/v1/employees/1/',
            {'first_name': 'John'},
            format='json'
        )
        self.assertEqual(response.status_code, 200)
    
    def test_patch_with_form_data(self):
        """Тест PATCH с form data"""
        response = self.client.patch(
            '/api/v1/employees/1/',
            {'first_name': 'John'},
            format='multipart'
        )
        self.assertEqual(response.status_code, 200)
    
    def test_missing_required_field(self):
        """Тест обработки отсутствующего поля"""
        response = self.client.patch(
            '/api/v1/employees/1/',
            {},
            format='json'
        )
        self.assertEqual(response.status_code, 400)
    
    def test_invalid_int_parameter(self):
        """Тест невалидного целочисленного параметра"""
        response = self.client.get('/api/v1/employees/?page=abc')
        # Должен вернуть 400 или использовать дефолт
        self.assertIn(response.status_code, [200, 400])
```

---

## Рекомендации по code review

### Чек-лист для PR

- [ ] Нет прямого доступа `request.data['key']` — только `.get()`
- [ ] Все `int()` обёрнуты в try/except или используют safe_int()
- [ ] Проверка типа для QueryDict/dict перед `.dict()`
- [ ] `.strip()` используется с проверкой на None
- [ ] Есть тесты для новых API endpoints
- [ ] Обработаны все edge cases (empty, None, invalid)

### GitHub Actions / CI

Добавить в `.github/workflows/quality.yml`:
```yaml
name: Code Quality

on: [push, pull_request]

jobs:
  audit:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Run code audit
        run: |
          cd backend
          bash scripts/audit_code_patterns.sh
          # Fail если найдены критичные проблемы
          ! grep -rn "request\.data\[" --include="*.py" . | grep -v "# noqa"
```

---

## Приоритеты исправления

1. **Срочно (в течение недели):**
   - Исправить все `request.data['key']` → `.get('key')`
   - Добавить обработку ValueError для int()

2. **Важно (в течение месяца):**
   - Настроить pre-commit hooks
   - Добавить mypy для статической типизации
   - Написать тесты для критичных API endpoints

3. **Желательно:**
   - Настроить CI/CD с автопроверкой
   - Провести code review всех найденных мест
   - Документировать паттерны в wiki

---

## Полезные ссылки

- [DRF Best Practices](https://www.django-rest-framework.org/api-guide/requests/)
- [Django Security Checklist](https://docs.djangoproject.com/en/5.0/howto/deployment/checklist/)
- [Python Type Hints](https://docs.python.org/3/library/typing.html)
