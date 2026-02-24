@echo off
REM Скрипт для проверки функции ответа на сообщение (Windows)
REM Запускает сервер и открывает тестовую страницу

echo.
echo 🧪 Проверка функции ответа на сообщение
echo ========================================
echo.

REM Проверка виртуального окружения
if not exist ".venv" (
    echo ❌ Виртуальное окружение не найдено
    echo Создайте его командой: python -m venv .venv
    exit /b 1
)

echo ✅ Виртуальное окружение найдено
echo.

REM Проверка Python в виртуальном окружении
if exist ".venv\Scripts\python.exe" (
    .venv\Scripts\python.exe --version
    echo ✅ Python найден в виртуальном окружении
) else (
    echo ❌ Python не найден в .venv\Scripts\
    exit /b 1
)

echo.
echo 📊 Что будет проверено:
echo   1. Контекстное меню -^> Ответить
echo   2. ChatFormManager (режим reply)
echo   3. Превью ответа в сообщениях
echo   4. Загрузка реакций (дефолтные)
echo.

echo 🚀 Запуск Django сервера...
echo.

REM Запуск сервера
start "Django Server" .venv\Scripts\python.exe manage.py runserver 9000

echo ⏳ Ожидание запуска сервера (5 сек)...
timeout /t 5 /nobreak > nul

echo.
echo ✅ Сервер запущен!
echo.
echo 📝 Откройте в браузере:
echo    http://localhost:9000/test_reply_functionality.html
echo.
echo 🌐 Или нажмите Enter чтобы открыть автоматически...
pause

REM Открыть браузер
start http://localhost:9000/test_reply_functionality.html

echo.
echo Закройте окно "Django Server" чтобы остановить сервер
echo.
pause
