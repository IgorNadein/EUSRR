"""
Общие константы и настройки для всех тестов.

Этот файл содержит переиспользуемые константы, URL-адреса и настройки,
чтобы избежать дублирования в тестовых файлах.
"""

# API endpoints base URLs
API_BASE_URL = "/api/v1/"
API_REQUESTS_URL = f"{API_BASE_URL}requests/"
API_EMPLOYEES_URL = f"{API_BASE_URL}employees/"
API_DEPARTMENTS_URL = f"{API_BASE_URL}departments/"
API_POSTS_URL = f"{API_BASE_URL}posts/"
API_COMMENTS_URL = f"{API_BASE_URL}comments/"
API_DOCUMENTS_URL = f"{API_BASE_URL}documents/"
API_AUTH_URL = f"{API_BASE_URL}auth/"
API_CALENDAR_URL = f"{API_BASE_URL}calendar/"
API_CHATS_URL = f"{API_BASE_URL}communications/chats/"
API_MESSAGES_URL = f"{API_BASE_URL}communications/messages/"

# Тестовые данные по умолчанию
DEFAULT_PASSWORD = "pass"
DEFAULT_TEST_PHONE_PREFIX = "+7999000"

# Email домены для тестов
TEST_EMAIL_DOMAIN = "example.com"

# Временные интервалы (в секундах)
TEST_TIMEOUT_SHORT = 5
TEST_TIMEOUT_MEDIUM = 30
TEST_TIMEOUT_LONG = 60

# Лимиты пагинации
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100

# Форматы файлов для тестирования
TEST_IMAGE_FORMATS = ["png", "jpg", "jpeg", "gif", "webp"]
TEST_DOCUMENT_FORMATS = ["pdf", "doc", "docx", "txt"]

# Размеры файлов для тестов (в байтах)
TEST_FILE_SIZE_SMALL = 1024  # 1 KB
TEST_FILE_SIZE_MEDIUM = 1024 * 100  # 100 KB
TEST_FILE_SIZE_LARGE = 1024 * 1024  # 1 MB

# Минимальная PNG картинка 1x1 (черный пиксель) в base64
TEST_IMAGE_1X1_PNG_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR4nGMA"
    "AQAABQABDQottAAAAABJRU5ErkJggg=="
)

# Data URI для тестовой картинки
TEST_IMAGE_DATA_URI = f"data:image/png;base64,{TEST_IMAGE_1X1_PNG_B64}"

# Настройки для тестирования LDAP (если используется)
LDAP_TEST_BASE_DN = "dc=test,dc=local"
LDAP_TEST_USER_DN = f"ou=users,{LDAP_TEST_BASE_DN}"
LDAP_TEST_GROUP_DN = f"ou=groups,{LDAP_TEST_BASE_DN}"
