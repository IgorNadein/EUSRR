"""
Примеры использования модернизированной системы логирования EUSRR.

Этот модуль демонстрирует best practices для логирования
в различных сценариях приложения.
"""

import logging
from functools import wraps
from time import time

# Инициализация логгеров для разных компонентов
logger = logging.getLogger(__name__)
ldap_logger = logging.getLogger('employees.ldap')
security_logger = logging.getLogger('django.security')


# ============================================================================
# Базовое логирование
# ============================================================================

def basic_logging_example():
    """Примеры базового логирования на разных уровнях."""
    
    # DEBUG: детальная информация для диагностики
    logger.debug("Начало обработки запроса")
    logger.debug("Параметры: limit=%d, offset=%d", 10, 0)
    
    # INFO: стандартные события жизненного цикла
    logger.info("Пользователь успешно авторизован: %s", "admin@example.com")
    logger.info("Создан новый документ ID=%d", 123)
    
    # WARNING: неожиданные ситуации, но не критичные
    logger.warning("Использован устаревший API endpoint: /api/v1/old")
    logger.warning("Попытка доступа к несуществующему ресурсу ID=%d", 999)
    
    # ERROR: ошибки, которые не останавливают приложение
    logger.error("Не удалось отправить email: %s", "smtp_error")
    
    # CRITICAL: критические ошибки
    logger.critical("Потеряно подключение к базе данных")


# ============================================================================
# Логирование с контекстом
# ============================================================================

def contextual_logging_example(user, document):
    """Логирование с дополнительным контекстом."""
    
    # Передача структурированных данных через extra
    logger.info(
        "Документ %s обработан пользователем %s",
        document.title,
        user.email,
        extra={
            'user_id': user.id,
            'user_email': user.email,
            'document_id': document.id,
            'document_type': document.doc_type,
            'action': 'process',
        }
    )
    
    # Лог будет содержать все переданные данные,
    # что упростит фильтрацию и анализ


# ============================================================================
# Логирование исключений
# ============================================================================

def exception_logging_example():
    """Правильное логирование исключений с трассировкой."""
    
    try:
        # Опасная операция
        result = 10 / 0
    except ZeroDivisionError:
        # exc_info=True добавляет полную трассировку стека
        logger.error("Ошибка при выполнении операции", exc_info=True)
    
    try:
        # Другая операция
        employee = Employee.objects.get(pk=99999)
    except Employee.DoesNotExist:
        # exception() - сокращение для error(..., exc_info=True)
        logger.exception("Сотрудник не найден: pk=99999")


# ============================================================================
# LDAP и безопасность
# ============================================================================

def security_logging_example(request, username):
    """Логирование событий безопасности."""
    
    # Успешная аутентификация
    ldap_logger.info(
        "LDAP аутентификация успешна: %s",
        username,
        extra={
            'username': username,
            'ip_address': request.META.get('REMOTE_ADDR'),
            'user_agent': request.META.get('HTTP_USER_AGENT'),
            'event': 'login_success',
        }
    )
    
    # Неудачная попытка входа
    security_logger.warning(
        "Неудачная попытка входа: %s",
        username,
        extra={
            'username': username,
            'ip_address': request.META.get('REMOTE_ADDR'),
            'reason': 'invalid_password',
            'event': 'login_failed',
        }
    )
    
    # Подозрительная активность
    security_logger.error(
        "Множественные неудачные попытки входа",
        extra={
            'username': username,
            'ip_address': request.META.get('REMOTE_ADDR'),
            'attempts': 5,
            'event': 'brute_force_attempt',
        }
    )


# ============================================================================
# Декоратор для логирования производительности
# ============================================================================

def log_performance(logger_name=None):
    """
    Декоратор для логирования времени выполнения функции.
    
    Usage:
        @log_performance('employees')
        def slow_operation():
            time.sleep(2)
    """
    def decorator(func):
        func_logger = logging.getLogger(logger_name or func.__module__)
        
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time()
            func_name = func.__qualname__
            
            func_logger.debug("Начало выполнения: %s", func_name)
            
            try:
                result = func(*args, **kwargs)
                elapsed = time() - start_time
                
                func_logger.info(
                    "Функция %s завершена за %.3f сек",
                    func_name,
                    elapsed,
                    extra={
                        'function': func_name,
                        'elapsed_time': elapsed,
                        'success': True,
                    }
                )
                
                return result
                
            except Exception as e:
                elapsed = time() - start_time
                
                func_logger.error(
                    "Ошибка в функции %s после %.3f сек: %s",
                    func_name,
                    elapsed,
                    str(e),
                    exc_info=True,
                    extra={
                        'function': func_name,
                        'elapsed_time': elapsed,
                        'success': False,
                        'error_type': type(e).__name__,
                    }
                )
                
                raise
        
        return wrapper
    return decorator


# ============================================================================
# Логирование в views
# ============================================================================

def view_logging_example(request):
    """Пример логирования в Django view."""
    
    # Логирование начала запроса
    logger.info(
        "Обработка запроса %s %s",
        request.method,
        request.path,
        extra={
            'method': request.method,
            'path': request.path,
            'user_id': request.user.id if request.user.is_authenticated else None,
            'ip': request.META.get('REMOTE_ADDR'),
        }
    )
    
    try:
        # Бизнес-логика
        data = process_request(request)
        
        logger.info("Запрос успешно обработан")
        return JsonResponse(data)
        
    except ValidationError as e:
        # Пользовательские ошибки - WARNING уровень
        logger.warning(
            "Ошибка валидации: %s",
            str(e),
            extra={'errors': e.message_dict}
        )
        return JsonResponse({'errors': e.message_dict}, status=400)
        
    except Exception as e:
        # Неожиданные ошибки - ERROR уровень
        logger.exception("Необработанная ошибка в view")
        return JsonResponse({'error': 'Internal server error'}, status=500)


# ============================================================================
# Логирование фоновых задач Celery
# ============================================================================

@log_performance('celery')
def celery_task_logging_example():
    """Пример логирования в Celery задаче."""
    
    task_logger = logging.getLogger('celery.tasks')
    
    task_logger.info("Начало выполнения задачи sync_ldap")
    
    try:
        # Выполнение задачи
        synced_count = 0
        error_count = 0
        
        for employee in Employee.objects.filter(is_active=True):
            try:
                employee.sync_to_ldap()
                synced_count += 1
                
                task_logger.debug("Синхронизирован Employee ID=%d", employee.id)
                
            except Exception as e:
                error_count += 1
                
                task_logger.error(
                    "Ошибка синхронизации Employee ID=%d: %s",
                    employee.id,
                    str(e),
                    extra={'employee_id': employee.id}
                )
        
        # Итоговый отчет
        task_logger.info(
            "Задача sync_ldap завершена: успешно=%d, ошибок=%d",
            synced_count,
            error_count,
            extra={
                'synced_count': synced_count,
                'error_count': error_count,
                'total': synced_count + error_count,
            }
        )
        
    except Exception as e:
        task_logger.exception("Критическая ошибка в задаче sync_ldap")
        raise


# ============================================================================
# Условное логирование
# ============================================================================

def conditional_logging_example(data):
    """Логирование в зависимости от условий."""
    
    # Логируем только если включен DEBUG уровень
    if logger.isEnabledFor(logging.DEBUG):
        # Дорогостоящая операция форматирования
        detailed_info = format_complex_data(data)
        logger.debug("Детальная информация: %s", detailed_info)
    
    # Всегда логируем важные события
    logger.info("Обработка завершена")


# ============================================================================
# Логирование Django Signals
# ============================================================================

def signal_logging_example(sender, instance, created, **kwargs):
    """Пример логирования в Django signal handler."""
    
    if created:
        logger.info(
            "Создан новый объект %s (ID=%d)",
            sender.__name__,
            instance.pk,
            extra={
                'model': sender.__name__,
                'object_id': instance.pk,
                'action': 'created',
            }
        )
    else:
        logger.debug(
            "Обновлен объект %s (ID=%d)",
            sender.__name__,
            instance.pk,
            extra={
                'model': sender.__name__,
                'object_id': instance.pk,
                'action': 'updated',
            }
        )


# ============================================================================
# Антипаттерны (чего НЕ делать)
# ============================================================================

def antipatterns_example():
    """Примеры неправильного использования логирования."""
    
    # ❌ НЕ ДЕЛАЙТЕ ТАК:
    
    # 1. Логирование чувствительных данных
    # logger.info("User password: %s", password)  # НИКОГДА!
    # logger.debug("API key: %s", api_key)  # НИКОГДА!
    
    # 2. Избыточное логирование в циклах
    # for i in range(10000):
    #     logger.debug("Processing item %d", i)  # Замедляет выполнение
    
    # 3. Использование print() вместо logger
    # print("Something happened")  # Используйте logger!
    
    # 4. Конкатенация строк в логах
    # logger.info("User " + user.email + " logged in")  # Неэффективно
    
    # 5. Логирование без контекста
    # logger.error("Error")  # Бесполезно без деталей
    
    # ✅ ПРАВИЛЬНО:
    
    # 1. Не логируем пароли, только факт действия
    logger.info("User authentication successful", extra={'username': username})
    
    # 2. Логируем суммарные результаты после цикла
    logger.info("Processed %d items", 10000)
    
    # 3. Всегда используем logger
    logger.info("Something happened")
    
    # 4. Используем форматирование
    logger.info("User %s logged in", user.email)
    
    # 5. Добавляем контекст
    logger.error("Database connection failed", extra={'host': db_host, 'port': db_port})


# ============================================================================
# Контекстный менеджер для логирования блоков кода
# ============================================================================

class LogContext:
    """
    Контекстный менеджер для логирования блоков кода.
    
    Usage:
        with LogContext('employees', 'Синхронизация с LDAP'):
            sync_employees()
    """
    
    def __init__(self, logger_name, operation_name):
        self.logger = logging.getLogger(logger_name)
        self.operation_name = operation_name
        self.start_time = None
    
    def __enter__(self):
        self.start_time = time()
        self.logger.info("Начало: %s", self.operation_name)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        elapsed = time() - self.start_time
        
        if exc_type is None:
            self.logger.info(
                "Завершено: %s (%.3f сек)",
                self.operation_name,
                elapsed,
                extra={'operation': self.operation_name, 'elapsed': elapsed}
            )
        else:
            self.logger.error(
                "Ошибка в: %s (%.3f сек): %s",
                self.operation_name,
                elapsed,
                str(exc_val),
                exc_info=True,
                extra={
                    'operation': self.operation_name,
                    'elapsed': elapsed,
                    'error_type': exc_type.__name__,
                }
            )
        
        return False  # Не подавляем исключение


# Пример использования контекстного менеджера
def context_manager_example():
    """Использование LogContext для логирования блоков кода."""
    
    with LogContext('employees', 'Импорт сотрудников из Excel'):
        # Код операции
        employees = import_from_excel('employees.xlsx')
        # Автоматически залогируется время выполнения
    
    # При ошибке автоматически залогируется с трассировкой
    try:
        with LogContext('employees.ldap', 'Синхронизация с AD'):
            sync_with_active_directory()
    except Exception:
        pass  # Уже залогировано в контекстном менеджере
