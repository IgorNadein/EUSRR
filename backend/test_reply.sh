#!/bin/bash

# Скрипт для проверки функции ответа на сообщение
# Запускает сервер и открывает тестовую страницу

echo "🧪 Проверка функции ответа на сообщение"
echo "========================================"
echo ""

# Проверка виртуального окружения
if [ ! -d ".venv" ]; then
    echo "❌ Виртуальное окружение не найдено"
    echo "Создайте его командой: python -m venv .venv"
    exit 1
fi

echo "✅ Виртуальное окружение найдено"

# Активация виртуального окружения (Windows)
if [ -f ".venv/Scripts/activate" ]; then
    source .venv/Scripts/activate
    echo "✅ Виртуальное окружение активировано"
else
    echo "⚠️ Не удалось активировать виртуальное окружение"
fi

# Проверка Python
python_version=$(python --version 2>&1)
echo "Python: $python_version"

echo ""
echo "📊 Что будет проверено:"
echo "  1. Контекстное меню -> Ответить"
echo "  2. ChatFormManager (режим reply)"
echo "  3. Превью ответа в сообщениях"
echo "  4. Загрузка реакций (дефолтные)"
echo ""

# Запуск сервера
echo "🚀 Запуск Django сервера..."
echo ""
python manage.py runserver 9000 &
SERVER_PID=$!

echo "Server PID: $SERVER_PID"
echo ""
echo "⏳ Ожидание запуска сервера (5 сек)..."
sleep 5

echo ""
echo "✅ Сервер запущен!"
echo ""
echo "📝 Откройте в браузере:"
echo "   http://localhost:9000/test_reply_functionality.html"
echo ""
echo "Нажмите Ctrl+C для остановки сервера"
echo ""

# Ожидание завершения
wait $SERVER_PID
