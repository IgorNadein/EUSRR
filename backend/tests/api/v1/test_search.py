# backend/tests/api/v1/test_search.py
"""
Тесты для глобального поиска через django-watson.
"""
import itertools
import pytest
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APIClient

from employees.models import Employee, Department, Position
from feed.models import Post
from requests_app.models import Request


_phone_counter = itertools.count(100_000_000)
_email_counter = itertools.count(1)


@pytest.fixture
def make_user(db):
    """Фабрика пользователей."""
    User = get_user_model()
    
    def _make_user(email=None, password="pass12345", **extra):
        if email is None:
            email = f"user{next(_email_counter)}@example.com"
        phone = extra.pop("phone_number", None) or f"+79{next(_phone_counter):09d}"
        user = User.objects.create_user(
            email=email,
            phone_number=phone,
            send_activation_email=False,
            **extra
        )
        if password:
            user.set_password(password)
            user.save()
        return user
    
    return _make_user


@pytest.fixture
def regular_user(make_user):
    """Обычный пользователь без спецправ."""
    return make_user(email="regular@example.com", first_name="Регуляр", last_name="Пользователь")


@pytest.fixture
def api_client(regular_user):
    """Авторизованный DRF-клиент."""
    client = APIClient()
    client.force_authenticate(user=regular_user)
    return client


@pytest.fixture
def sample_data(db):
    """Создаёт тестовые данные для поиска."""
    # Отделы
    dept_it = Department.objects.create(name="IT отдел", description="Информационные технологии")
    dept_hr = Department.objects.create(name="HR отдел", description="Управление персоналом")
    
    # Должности
    pos_dev = Position.objects.create(name="Разработчик", description="Python/Django разработчик")
    pos_manager = Position.objects.create(name="Менеджер", description="HR менеджер")
    
    # Сотрудники
    emp1 = Employee.objects.create(
        email="ivanov@test.com",
        first_name="Иван",
        last_name="Иванов",
        patronymic="Иванович",
        position=pos_dev,
        phone_number="+79001234567"
    )
    emp1.departments_links.create(department=dept_it)
    
    emp2 = Employee.objects.create(
        email="petrov@test.com",
        first_name="Пётр",
        last_name="Петров",
        patronymic="Петрович",
        position=pos_manager,
        phone_number="+79007654321"
    )
    emp2.departments_links.create(department=dept_hr)
    
    # Посты
    post1 = Post.objects.create(
        author=emp1,
        title="Новые технологии в разработке",
        body="Сегодня мы внедрили новый фреймворк Django для нашего проекта"
    )
    
    post2 = Post.objects.create(
        author=emp2,
        title="Вакансии в HR отделе",
        body="Требуется менеджер по подбору персонала"
    )
    
    # Заявления
    req1 = Request.objects.create(
        employee=emp1,
        title="Заявка на отпуск",
        comment="Прошу предоставить отпуск с 1 по 14 февраля",
        type="vacation",
        status="pending"
    )
    
    return {
        'departments': [dept_it, dept_hr],
        'employees': [emp1, emp2],
        'posts': [post1, post2],
        'requests': [req1],
    }


@pytest.mark.django_db
class TestSearchAPI:
    """Тесты для API /api/v1/search/"""
    
    def test_search_requires_authentication(self, client):
        """Поиск требует аутентификации."""
        response = client.get('/api/v1/search/?q=test')
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    def test_search_empty_query(self, api_client):
        """Пустой запрос возвращает пустые результаты."""
        response = api_client.get('/api/v1/search/?q=')
        assert response.status_code == status.HTTP_200_OK
        assert response.data['query'] == ''
        assert response.data['total'] == 0
        assert len(response.data['results']) == 0
    
    def test_search_no_results(self, api_client, sample_data):
        """Поиск без результатов."""
        # Пересоздаём индексы watson для тестовых данных
        from django.core.management import call_command
        call_command('buildwatson', verbosity=0)
        
        response = api_client.get('/api/v1/search/?q=несуществующийтекст12345')
        assert response.status_code == status.HTTP_200_OK
        assert response.data['total'] == 0
    
    def test_search_finds_employee_by_name(self, api_client, sample_data):
        """Поиск находит сотрудника по имени."""
        from django.core.management import call_command
        call_command('buildwatson', verbosity=0)
        
        response = api_client.get('/api/v1/search/?q=Иванов')
        assert response.status_code == status.HTTP_200_OK
        assert response.data['total'] > 0
        assert 'employee' in response.data['counts']
        
        # Проверяем, что в результатах есть сотрудник
        employees = [r for r in response.data['results'] if r['model_name'] == 'employee']
        assert len(employees) > 0
        assert 'Иванов' in employees[0]['title']
    
    def test_search_finds_employee_by_email(self, api_client, sample_data):
        """Поиск находит сотрудника по email."""
        from django.core.management import call_command
        call_command('buildwatson', verbosity=0)
        
        response = api_client.get('/api/v1/search/?q=ivanov@test.com')
        assert response.status_code == status.HTTP_200_OK
        
        employees = [r for r in response.data['results'] if r['model_name'] == 'employee']
        assert len(employees) > 0
        assert 'ivanov@test.com' in employees[0]['meta']['email'].lower()
    
    def test_search_finds_department(self, api_client, sample_data):
        """Поиск находит отдел."""
        from django.core.management import call_command
        call_command('buildwatson', verbosity=0)
        
        response = api_client.get('/api/v1/search/?q=IT')
        assert response.status_code == status.HTTP_200_OK
        
        departments = [r for r in response.data['results'] if r['model_name'] == 'department']
        assert len(departments) > 0
        assert 'IT' in departments[0]['title']
    
    def test_search_finds_post(self, api_client, sample_data):
        """Поиск находит пост."""
        from django.core.management import call_command
        call_command('buildwatson', verbosity=0)
        
        response = api_client.get('/api/v1/search/?q=Django')
        assert response.status_code == status.HTTP_200_OK
        
        posts = [r for r in response.data['results'] if r['model_name'] == 'post']
        assert len(posts) > 0
        assert 'Django' in posts[0]['description'] or 'Django' in posts[0]['title']
    
    def test_search_finds_request(self, api_client, sample_data):
        """Поиск находит заявление."""
        from django.core.management import call_command
        call_command('buildwatson', verbosity=0)
        
        # Авторизуемся как автор заявления
        emp = sample_data['employees'][0]
        api_client.force_authenticate(user=emp)
        
        response = api_client.get('/api/v1/search/?q=отпуск')
        assert response.status_code == status.HTTP_200_OK
        
        requests = [r for r in response.data['results'] if r['model_name'] == 'request']
        assert len(requests) > 0
        assert 'отпуск' in requests[0]['title'].lower()
    
    def test_search_limit_parameter(self, api_client, sample_data):
        """Параметр limit ограничивает количество результатов на тип."""
        from django.core.management import call_command
        call_command('buildwatson', verbosity=0)
        
        # Создадим больше 2 постов
        emp = sample_data['employees'][0]
        for i in range(5):
            Post.objects.create(
                author=emp,
                title=f"Тестовый пост {i}",
                body="Django разработка"
            )
        call_command('buildwatson', verbosity=0)
        
        response = api_client.get('/api/v1/search/?q=Django&limit=2')
        assert response.status_code == status.HTTP_200_OK
        
        posts = [r for r in response.data['results'] if r['model_name'] == 'post']
        assert len(posts) <= 2
    
    def test_search_response_structure(self, api_client, sample_data):
        """Проверка структуры ответа API."""
        from django.core.management import call_command
        call_command('buildwatson', verbosity=0)
        
        response = api_client.get('/api/v1/search/?q=Иванов')
        assert response.status_code == status.HTTP_200_OK
        
        # Проверяем ключи верхнего уровня
        assert 'query' in response.data
        assert 'results' in response.data
        assert 'counts' in response.data
        assert 'total' in response.data
        
        # Проверяем структуру результата
        if len(response.data['results']) > 0:
            result = response.data['results'][0]
            assert 'model_name' in result
            assert 'object_id' in result
            assert 'title' in result
            assert 'url' in result
    
    def test_search_request_permissions(self, api_client, sample_data):
        """Пользователи видят только свои заявления."""
        from django.core.management import call_command
        call_command('buildwatson', verbosity=0)
        
        emp1 = sample_data['employees'][0]
        emp2 = sample_data['employees'][1]
        
        # Создаём заявление от emp1
        Request.objects.create(
            employee=emp1,
            title="Личная заявка Иванова",
            comment="Конфиденциально",
            type="vacation",
            status="pending"
        )
        call_command('buildwatson', verbosity=0)
        
        # Авторизуемся как emp2
        api_client.force_authenticate(user=emp2)
        
        response = api_client.get('/api/v1/search/?q=Иванова')
        assert response.status_code == status.HTTP_200_OK
        
        # emp2 не должен видеть заявку emp1
        requests = [r for r in response.data['results'] if r['model_name'] == 'request']
        for req in requests:
            # Если есть заявления в результатах, они не должны быть от emp1
            if 'Личная заявка' in req['title']:
                pytest.fail("Пользователь видит чужое заявление")
    
    def test_search_cyrillic_query(self, api_client, sample_data):
        """Поиск по кириллице работает корректно."""
        from django.core.management import call_command
        call_command('buildwatson', verbosity=0)
        
        response = api_client.get('/api/v1/search/?q=технологии')
        assert response.status_code == status.HTTP_200_OK
        
        # Должны найти пост "Новые технологии в разработке"
        posts = [r for r in response.data['results'] if r['model_name'] == 'post']
        assert len(posts) > 0


@pytest.mark.django_db
class TestSearchIndexing:
    """Тесты индексации watson."""
    
    def test_watson_index_auto_updates(self, api_client, sample_data):
        """Индекс watson обновляется автоматически при изменении данных."""
        from django.core.management import call_command
        call_command('buildwatson', verbosity=0)
        
        # Создаём нового сотрудника
        new_emp = Employee.objects.create(
            email="sidorov@test.com",
            first_name="Сидор",
            last_name="Сидоров",
            patronymic="Сидорович",
        )
        
        # watson должен автоматически добавить в индекс
        response = api_client.get('/api/v1/search/?q=Сидоров')
        assert response.status_code == status.HTTP_200_OK
        
        employees = [r for r in response.data['results'] if r['model_name'] == 'employee']
        assert len(employees) > 0
        assert 'Сидоров' in employees[0]['title']
