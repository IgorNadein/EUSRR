#!/bin/bash
# Скрипт для управления LDAP тестами

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Цвета для вывода
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

function print_green() {
    echo -e "${GREEN}$1${NC}"
}

function print_yellow() {
    echo -e "${YELLOW}$1${NC}"
}

function print_red() {
    echo -e "${RED}$1${NC}"
}

function start_ldap() {
    print_yellow "🐳 Запуск LDAP сервера..."
    docker-compose -f docker-compose.test.yml up -d
    
    print_yellow "⏳ Ожидание запуска сервера (10 сек)..."
    sleep 10
    
    if docker ps | grep -q "eusrr-test-ldap"; then
        print_green "✅ LDAP сервер запущен"
        print_green "   - LDAP: ldap://localhost:10389"
        print_green "   - Admin UI: http://localhost:8090"
        print_green "   - Admin DN: cn=admin,dc=test,dc=local"
        print_green "   - Password: test_change-me-redacted-secret"
        
        # Загружаем базовую структуру если её ещё нет
        print_yellow "📋 Проверка базовой структуры LDAP..."
        if ldapsearch -x -H ldap://localhost:10389 \
            -b "ou=Users,dc=test,dc=local" \
            -D "cn=admin,dc=test,dc=local" \
            -w "test_change-me-redacted-secret" \
            2>/dev/null | grep -q "ou=Users"; then
            print_green "✅ Базовая структура уже загружена"
        else
            print_yellow "📥 Загрузка базовой структуры..."
            if [ -f "tests/ldap_fixtures/01-base-structure.ldif" ]; then
                ldapadd -x -H ldap://localhost:10389 \
                    -D "cn=admin,dc=test,dc=local" \
                    -w "test_change-me-redacted-secret" \
                    -f tests/ldap_fixtures/01-base-structure.ldif \
                    2>/dev/null && print_green "✅ Базовая структура загружена" || print_yellow "⚠️  Не удалось загрузить структуру (возможно уже существует)"
            else
                print_yellow "⚠️  Файл tests/ldap_fixtures/01-base-structure.ldif не найден"
            fi
        fi
    else
        print_red "❌ Не удалось запустить LDAP сервер"
        exit 1
    fi
}

function stop_ldap() {
    print_yellow "🛑 Остановка LDAP сервера..."
    docker-compose -f docker-compose.test.yml stop
    print_green "✅ LDAP сервер остановлен"
}

function restart_ldap() {
    print_yellow "🔄 Перезапуск LDAP сервера..."
    docker-compose -f docker-compose.test.yml restart
    sleep 5
    print_green "✅ LDAP сервер перезапущен"
}

function clean_ldap() {
    print_yellow "🧹 Очистка данных LDAP..."
    docker-compose -f docker-compose.test.yml down -v
    rm -rf ldap_test_data ldap_test_config
    print_green "✅ Данные LDAP удалены"
}

function status_ldap() {
    print_yellow "📊 Статус LDAP сервера:"
    docker-compose -f docker-compose.test.yml ps
}

function logs_ldap() {
    print_yellow "📋 Логи LDAP сервера:"
    docker logs eusrr-test-ldap -f
}

function test_ldap() {
    print_yellow "🧪 Запуск интеграционных тестов..."
    
    # Проверяем что сервер запущен
    if ! docker ps | grep -q "eusrr-test-ldap"; then
        print_red "❌ LDAP сервер не запущен. Запустите: ./ldap-test.sh start"
        exit 1
    fi
    
    # Запускаем тесты
    pytest -m integration tests/integration/ -v "$@"
}

function test_unit() {
    print_yellow "🧪 Запуск unit тестов (без LDAP)..."
    pytest tests/api/v1/employees/test_ldap_optional_*.py -v "$@"
}

function test_all() {
    print_yellow "🧪 Запуск всех тестов..."
    test_unit "$@"
    if docker ps | grep -q "eusrr-test-ldap"; then
        test_ldap "$@"
    else
        print_yellow "⚠️  LDAP сервер не запущен, интеграционные тесты пропущены"
    fi
}

function check_ldap() {
    print_yellow "🔍 Проверка подключения к LDAP..."
    
    if command -v ldapsearch &> /dev/null; then
        ldapsearch -x -H ldap://localhost:10389 \
            -b "dc=test,dc=local" \
            -D "cn=admin,dc=test,dc=local" \
            -w test_change-me-redacted-secret
    else
        print_yellow "ℹ️  ldapsearch не установлен, используем docker exec..."
        docker exec eusrr-test-ldap ldapsearch -x \
            -b "dc=test,dc=local" \
            -D "cn=admin,dc=test,dc=local" \
            -w test_change-me-redacted-secret
    fi
}

function show_help() {
    cat << EOF
🧪 LDAP Test Manager

Использование: ./ldap-test.sh [команда]

Команды:
  start       Запустить LDAP сервер
  stop        Остановить LDAP сервер
  restart     Перезапустить LDAP сервер
  clean       Удалить данные LDAP и контейнеры
  status      Показать статус сервера
  logs        Показать логи сервера
  check       Проверить подключение к LDAP
  
  test        Запустить интеграционные тесты
  test-unit   Запустить unit тесты (без LDAP)
  test-all    Запустить все тесты
  
  help        Показать эту справку

Примеры:
  ./ldap-test.sh start
  ./ldap-test.sh test
  ./ldap-test.sh test -k "register"
  ./ldap-test.sh logs
  ./ldap-test.sh clean && ./ldap-test.sh start

EOF
}

# Главная логика
case "${1:-help}" in
    start)
        start_ldap
        ;;
    stop)
        stop_ldap
        ;;
    restart)
        restart_ldap
        ;;
    clean)
        clean_ldap
        ;;
    status)
        status_ldap
        ;;
    logs)
        logs_ldap
        ;;
    check)
        check_ldap
        ;;
    test)
        shift
        test_ldap "$@"
        ;;
    test-unit)
        shift
        test_unit "$@"
        ;;
    test-all)
        shift
        test_all "$@"
        ;;
    help|--help|-h)
        show_help
        ;;
    *)
        print_red "❌ Неизвестная команда: $1"
        echo ""
        show_help
        exit 1
        ;;
esac
