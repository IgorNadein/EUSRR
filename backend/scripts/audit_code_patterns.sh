#!/bin/bash
# Аудит потенциально проблемных паттернов в коде

echo "=== Поиск потенциальных проблем ==="
echo ""

echo "1. Небезопасный доступ к request.data:"
grep -rn "request\.data\[" --include="*.py" . | grep -v "# noqa" || echo "✓ Не найдено"
echo ""

echo "2. Использование .dict() без проверки типа:"
grep -rn "\.data\.dict()" --include="*.py" . | grep -v "hasattr" || echo "✓ Не найдено"
echo ""

echo "3. Прямое обращение к QueryDict без .get():"
grep -rn "request\.POST\[" --include="*.py" . | grep -v "# noqa" || echo "✓ Не найдено"
echo ""

echo "4. Небезопасный int() без try/except:"
grep -rn "int(.*request\." --include="*.py" . | head -20
echo ""

echo "5. Отсутствие проверки на None перед .strip():"
grep -rn "\.strip()" --include="*.py" . | grep -v "if.*:" | head -10
echo ""

echo "=== Аудит завершен ==="
