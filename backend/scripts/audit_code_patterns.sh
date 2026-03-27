#!/bin/bash
# Аудит потенциально проблемных паттернов в коде
# Исключает .venv/ (сторонние пакеты)

echo "=== Поиск потенциальных проблем ==="
echo ""

echo "1. Небезопасный доступ к request.data:"
grep -rn "request\.data\[" --include="*.py" . --exclude-dir=.venv | grep -v "# noqa" || echo "✓ Не найдено"
echo ""

echo "2. Использование .dict() без проверки типа:"
grep -rn "\.data\.dict()" --include="*.py" . --exclude-dir=.venv | grep -v "hasattr" || echo "✓ Не найдено"
echo ""

echo "3. Прямое обращение к QueryDict без .get():"
grep -rn "request\.POST\[" --include="*.py" . --exclude-dir=.venv | grep -v "# noqa" || echo "✓ Не найдено"
echo ""

echo "4. Небезопасный int() без try/except:"
grep -rn "int(.*request\." --include="*.py" . --exclude-dir=.venv | head -20
echo ""

echo "5. Отсутствие проверки на None перед .strip():"
grep -rn "\.strip()" --include="*.py" . --exclude-dir=.venv | grep -v "if.*:" | head -10
echo ""

echo "=== Аудит завершен ==="
