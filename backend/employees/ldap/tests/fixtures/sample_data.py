"""
Примеры тестовых данных и фикстур для LDAP тестов.

Этот модуль содержит готовые тестовые данные, которые можно использовать
в тестах вместо создания их каждый раз заново.
"""

from employees.ldap.domain.dtos import DirectoryUserDTO, DirectoryDepartmentDTO


# ==================== Тестовые пользователи ====================

SAMPLE_USERS = [
    DirectoryUserDTO(
        first_name="Иван",
        last_name="Иванов",
        patronymic="Петрович",
        email="ivanov@example.com",
        phone="+79001234567",
        password="TestPass123!",
        avatar=None,
        groups=["Developers", "Users"]
    ),
    DirectoryUserDTO(
        first_name="Мария",
        last_name="Петрова",
        patronymic="Сергеевна",
        email="petrova@example.com",
        phone="+79007654321",
        password="TestPass456!",
        avatar=None,
        groups=["HR", "Users"]
    ),
    DirectoryUserDTO(
        first_name="Алексей",
        last_name="Сидоров",
        patronymic="Александрович",
        email="sidorov@example.com",
        phone="+79009876543",
        password="TestPass789!",
        avatar=None,
        groups=["Management", "Users"]
    ),
]


# ==================== Тестовые отделы ====================

SAMPLE_DEPARTMENTS = [
    DirectoryDepartmentDTO(
        name="IT Отдел",
        parent=None,
        head=None
    ),
    DirectoryDepartmentDTO(
        name="HR Отдел",
        parent=None,
        head=None
    ),
    DirectoryDepartmentDTO(
        name="Отдел разработки",
        parent=None,  # Будет установлен в тестах как IT Отдел
        head=None
    ),
]


# ==================== Тестовые LDAP DN ====================

SAMPLE_DNS = {
    'users': [
        'CN=Иван Иванов,OU=Users,DC=example,DC=com',
        'CN=Мария Петрова,OU=Users,DC=example,DC=com',
        'CN=Алексей Сидоров,OU=Users,DC=example,DC=com',
    ],
    'departments': [
        'OU=IT,DC=example,DC=com',
        'OU=HR,DC=example,DC=com',
        'OU=Development,OU=IT,DC=example,DC=com',
    ],
    'groups': [
        'CN=Developers,OU=Groups,DC=example,DC=com',
        'CN=HR,OU=Groups,DC=example,DC=com',
        'CN=Management,OU=Groups,DC=example,DC=com',
        'CN=Users,OU=Groups,DC=example,DC=com',
    ],
    'positions': [
        'CN=POS_1,OU=Positions,DC=example,DC=com',
        'CN=POS_2,OU=Positions,DC=example,DC=com',
        'CN=POS_3,OU=Positions,DC=example,DC=com',
    ],
}


# ==================== Тестовые LDAP атрибуты ====================

SAMPLE_LDAP_ATTRIBUTES = {
    'user': {
        'cn': 'Иван Иванов',
        'sAMAccountName': 'ivanov',
        'userPrincipalName': 'ivanov@example.com',
        'givenName': 'Иван',
        'sn': 'Иванов',
        'displayName': 'Иван Петрович Иванов',
        'mail': 'ivanov@example.com',
        'telephoneNumber': '+79001234567',
        'userAccountControl': 512,  # Normal account
        'objectClass': ['top', 'person', 'organizationalPerson', 'user'],
    },
    'group': {
        'cn': 'Developers',
        'sAMAccountName': 'Developers',
        'description': 'Development team',
        'member': [
            'CN=Иван Иванов,OU=Users,DC=example,DC=com',
            'CN=Мария Петрова,OU=Users,DC=example,DC=com',
        ],
        'objectClass': ['top', 'group'],
        'groupType': -2147483646,  # Global security group
    },
    'ou': {
        'ou': 'IT',
        'name': 'IT',
        'description': 'IT Department',
        'objectClass': ['top', 'organizationalUnit'],
    },
}


# ==================== Тестовые LDAP фильтры ====================

SAMPLE_LDAP_FILTERS = {
    'all_users': '(&(objectClass=user)(objectCategory=person))',
    'active_users': (
        '(&(objectClass=user)(objectCategory=person)'
        '(!(userAccountControl:1.2.840.113556.1.4.803:=2)))'
    ),
    'all_groups': '(objectClass=group)',
    'group_by_name': '(&(objectClass=group)(cn={name}))',
    'user_by_login': (
        '(&(objectClass=user)(objectCategory=person)'
        '(sAMAccountName={login}))'
    ),
    'groups_with_member': (
        '(&(objectClass=group)(member={dn}))'
    ),
}


# ==================== Тестовые настройки ====================

TEST_LDAP_SETTINGS = {
    'LDAP_HOST': 'ldaps://test.example.com:636',
    'LDAP_BASE_DN': 'DC=example,DC=com',
    'LDAP_BIND_DN': 'CN=ServiceAccount,DC=example,DC=com',
    'LDAP_BIND_PASSWORD': 'TestPassword123!',
    'LDAP_USERS_BASE': 'OU=Users,DC=example,DC=com',
    'LDAP_GROUPS_BASE': 'OU=Groups,DC=example,DC=com',
    'LDAP_POSITIONS_BASE': 'OU=Positions,DC=example,DC=com',
    'LDAP_UPN_SUFFIX': '@example.com',
    'LDAP_CONNECT_TIMEOUT': 5,
    'LDAP_RECEIVE_TIMEOUT': 10,
}


# ==================== Вспомогательные функции ====================

def create_test_user_dto(
    first_name="Test",
    last_name="User",
    email=None,
    **kwargs
):
    """
    Создает тестовый DirectoryUserDTO с настраиваемыми параметрами.
    
    Args:
        first_name: Имя
        last_name: Фамилия
        email: Email (по умолчанию генерируется из имени)
        **kwargs: Дополнительные параметры
    
    Returns:
        DirectoryUserDTO
    """
    if email is None:
        email = f"{last_name.lower()}@example.com"
    
    return DirectoryUserDTO(
        first_name=first_name,
        last_name=last_name,
        email=email,
        password=kwargs.get('password', 'TestPass123!'),
        patronymic=kwargs.get('patronymic', 'Тестович'),
        phone=kwargs.get('phone', '+79001234567'),
        avatar=kwargs.get('avatar'),
        groups=kwargs.get('groups', ['Users'])
    )


def create_test_department_dto(
    name="Test Department",
    short_name=None,
    **kwargs
):
    """
    Создает тестовый DirectoryDepartmentDTO с настраиваемыми параметрами.
    
    Args:
        name: Название отдела
        short_name: Короткое название (по умолчанию из name)
        **kwargs: Дополнительные параметры
    
    Returns:
        DirectoryDepartmentDTO
    """
    if short_name is None:
        short_name = ''.join([w[0] for w in name.split()])
    
    return DirectoryDepartmentDTO(
        name=name,
        parent=kwargs.get('parent'),
        head=kwargs.get('head')
    )


def create_test_ldap_entry(dn, attributes=None):
    """
    Создает mock LDAP entry с заданными атрибутами.
    
    Args:
        dn: Distinguished Name
        attributes: Словарь атрибутов
    
    Returns:
        Mock объект LDAP entry
    """
    from unittest.mock import Mock
    
    entry = Mock()
    entry.entry_dn = dn
    
    if attributes:
        for attr_name, attr_value in attributes.items():
            attr_mock = Mock()
            attr_mock.value = attr_value
            setattr(entry, attr_name, attr_mock)
    
    return entry


def generate_test_dns(count=10, ou='Users'):
    """
    Генерирует список тестовых DN.
    
    Args:
        count: Количество DN
        ou: Organizational Unit
    
    Returns:
        List[str]: Список DN
    """
    return [
        f'CN=User{i},OU={ou},DC=example,DC=com'
        for i in range(1, count + 1)
    ]


def get_sample_user_attributes(index=0):
    """
    Возвращает атрибуты тестового пользователя.
    
    Args:
        index: Индекс пользователя (0-2)
    
    Returns:
        dict: Словарь LDAP атрибутов
    """
    users = [
        {
            'cn': 'Иван Иванов',
            'sAMAccountName': 'ivanov',
            'userPrincipalName': 'ivanov@example.com',
            'givenName': 'Иван',
            'sn': 'Иванов',
            'mail': 'ivanov@example.com',
            'telephoneNumber': '+79001234567',
        },
        {
            'cn': 'Мария Петрова',
            'sAMAccountName': 'petrova',
            'userPrincipalName': 'petrova@example.com',
            'givenName': 'Мария',
            'sn': 'Петрова',
            'mail': 'petrova@example.com',
            'telephoneNumber': '+79007654321',
        },
        {
            'cn': 'Алексей Сидоров',
            'sAMAccountName': 'sidorov',
            'userPrincipalName': 'sidorov@example.com',
            'givenName': 'Алексей',
            'sn': 'Сидоров',
            'mail': 'sidorov@example.com',
            'telephoneNumber': '+79009876543',
        },
    ]
    
    return users[index % len(users)]
