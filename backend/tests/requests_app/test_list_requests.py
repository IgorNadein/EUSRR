"""
Тесты API: GET /api/v1/requests/ - список заявок
Проверяет логику доступа для различных типов пользователей
"""
import pytest

from requests_app.models import Request


pytestmark = pytest.mark.django_db


class TestListRequestsRegularUser:
    """Тесты для обычных пользователей без прав"""
    
    url = '/api/v1/requests/'
    
    def test_can_see_own_requests(self, auth_client_factory, test_employee):
        """1.1.1: Обычный пользователь видит свои заявки"""
        # Создаем заявку
        request = Request.objects.create(
            employee=test_employee,
            type='other',
            title='Моя заявка'
        )
        
        client = auth_client_factory(test_employee)
        response = client.get(self.url)
        
        assert response.status_code == 200
        assert response.data['count'] >= 1
        ids = [r['id'] for r in response.data['results']]
        assert request.id in ids
    
    def test_cannot_see_others_requests(
        self, auth_client_factory, test_employee, test_employee_second
    ):
        """1.1.3: Обычный пользователь НЕ видит чужие заявки"""
        # test_employee_second создает заявку
        other_request = Request.objects.create(
            employee=test_employee_second,
            type='other',
            title='Чужая заявка'
        )
        
        # test_employee пытается получить список
        client = auth_client_factory(test_employee)
        response = client.get(self.url)
        
        assert response.status_code == 200
        ids = [r['id'] for r in response.data['results']]
        assert other_request.id not in ids
    
    def test_can_see_request_addressed_to_him(
        self, auth_client_factory, test_employee, test_employee_second,
        create_request_helper
    ):
        """1.1.4: Пользователь видит заявку, где он в recipients"""
        # test_employee_second создает заявку для test_employee
        request = create_request_helper(
            employee=test_employee_second,
            recipients=[test_employee],
            title='Заявка для меня'
        )
        
        client = auth_client_factory(test_employee)
        response = client.get(self.url)
        
        assert response.status_code == 200
        ids = [r['id'] for r in response.data['results']]
        assert request.id in ids
    
    def test_can_see_request_cc(
        self, auth_client_factory, test_employee, test_employee_second,
        create_request_helper
    ):
        """1.1.5: Пользователь видит заявку, где он в cc_users"""
        # test_employee_second создает заявку с test_employee в CC
        request = create_request_helper(
            employee=test_employee_second,
            cc_users=[test_employee],
            title='Заявка CC'
        )
        
        client = auth_client_factory(test_employee)
        response = client.get(self.url)
        
        assert response.status_code == 200
        ids = [r['id'] for r in response.data['results']]
        assert request.id in ids
    
    def test_can_see_request_all_department(
        self, auth_client_factory, test_employee, test_employee_second,
        test_department, create_request_helper
    ):
        """1.1.6: Пользователь видит заявку sent_to_all_department его отдела"""
        # Добавляем test_employee в отдел
        from employees.models import EmployeeDepartment
        EmployeeDepartment.objects.create(
            employee=test_employee,
            department=test_department,
            is_active=True
        )
        
        # test_employee_second создает заявку "Всем в отделе"
        request = create_request_helper(
            employee=test_employee_second,
            departments=[test_department],
            sent_to_all=True,
            title='Всем в IT'
        )
        
        client = auth_client_factory(test_employee)
        response = client.get(self.url)
        
        assert response.status_code == 200
        ids = [r['id'] for r in response.data['results']]
        assert request.id in ids
    
    def test_cannot_see_all_department_other_dept(
        self, auth_client_factory, test_employee, test_employee_second,
        test_department, create_request_helper
    ):
        """1.1.7: Пользователь НЕ видит sent_to_all_department чужого отдела"""
        # test_employee НЕ в test_department
        # test_employee_second создает заявку "Всем в отделе"
        request = create_request_helper(
            employee=test_employee_second,
            departments=[test_department],
            sent_to_all=True,
            title='Всем в IT (но я не в IT)'
        )
        
        client = auth_client_factory(test_employee)
        response = client.get(self.url)
        
        assert response.status_code == 200
        ids = [r['id'] for r in response.data['results']]
        assert request.id not in ids
    
    def test_filter_mine(
        self, auth_client_factory, test_employee, test_employee_second,
        create_request_helper
    ):
        """1.1.8: Фильтр ?mine=true показывает только свои заявки"""
        # Создаем свою заявку
        my_request = create_request_helper(
            employee=test_employee,
            title='Моя заявка'
        )
        
        # Создаем заявку, адресованную test_employee
        addressed_request = create_request_helper(
            employee=test_employee_second,
            recipients=[test_employee],
            title='Адресованная мне'
        )
        
        client = auth_client_factory(test_employee)
        response = client.get(self.url, {'mine': 'true'})
        
        assert response.status_code == 200
        ids = [r['id'] for r in response.data['results']]
        
        # Должна быть только своя
        assert my_request.id in ids
        assert addressed_request.id not in ids
    
    def test_filter_addressed_to_me(
        self, auth_client_factory, test_employee, test_employee_second,
        test_employee_third, create_request_helper
    ):
        """1.1.9: Фильтр ?addressed_to_me=true показывает только адресованные"""
        # Создаем свою заявку
        my_request = create_request_helper(
            employee=test_employee,
            title='Моя заявка'
        )
        
        # Создаем заявку, адресованную test_employee
        addressed = create_request_helper(
            employee=test_employee_second,
            recipients=[test_employee],
            title='Адресованная мне'
        )
        
        # Создаем заявку, адресованную другому
        not_addressed = create_request_helper(
            employee=test_employee_second,
            recipients=[test_employee_third],
            title='Адресованная другому'
        )
        
        client = auth_client_factory(test_employee)
        response = client.get(self.url, {'addressed_to_me': 'true'})
        
        assert response.status_code == 200
        ids = [r['id'] for r in response.data['results']]
        
        # Должна быть адресованная, но не своя и не чужая
        assert addressed.id in ids
        assert my_request.id not in ids
        assert not_addressed.id not in ids


class TestListRequestsDeptHead:
    """Тесты для руководителей отделов"""
    
    url = '/api/v1/requests/'
    
    def test_can_see_department_requests(
        self, auth_client_factory, test_department, test_employee_second,
        create_request_helper, user_factory
    ):
        """1.2.1: Руководитель видит заявки сотрудников своего отдела"""
        # Создаем руководителя с помощью user_factory
        from employees.models import EmployeeDepartment
        
        head = user_factory(email='head@test.com')
        
        # Назначаем руководителем
        test_department.head = head
        test_department.save()
        
        # Добавляем в отдел
        EmployeeDepartment.objects.create(
            employee=head,
            department=test_department,
            is_active=True
        )
        
        # Добавляем test_employee_second в отдел
        EmployeeDepartment.objects.create(
            employee=test_employee_second,
            department=test_department,
            is_active=True
        )
        
        # test_employee_second создает заявку
        request = create_request_helper(
            employee=test_employee_second,
            title='Заявка сотрудника'
        )
        
        client = auth_client_factory(head)
        response = client.get(self.url)
        
        assert response.status_code == 200
        ids = [r['id'] for r in response.data['results']]
        assert request.id in ids


class TestListRequestsGlobalViewer:
    """Тесты для пользователей с глобальным правом can_view_all_requests"""
    
    url = '/api/v1/requests/'
    
    def test_can_see_all_requests(
        self, auth_client_factory, global_viewer, test_employee,
        test_employee_second, create_request_helper
    ):
        """1.5.1: Пользователь с can_view_all_requests видит ВСЕ заявки"""
        # Создаем несколько заявок от разных пользователей
        req1 = create_request_helper(
            employee=test_employee,
            title='Заявка 1'
        )
        req2 = create_request_helper(
            employee=test_employee_second,
            title='Заявка 2'
        )
        
        client = auth_client_factory(global_viewer)
        response = client.get(self.url)
        
        assert response.status_code == 200
        ids = [r['id'] for r in response.data['results']]
        
        # Должен видеть обе
        assert req1.id in ids
        assert req2.id in ids


class TestListRequestsStaff:
    """Тесты для Django staff пользователей"""
    
    url = '/api/v1/requests/'
    
    def test_staff_can_see_all_requests(
        self, auth_client_factory, test_staff_user, test_employee,
        test_employee_second, create_request_helper
    ):
        """1.6.1: Staff видит ВСЕ заявки"""
        # Создаем заявки
        req1 = create_request_helper(
            employee=test_employee,
            title='Заявка 1'
        )
        req2 = create_request_helper(
            employee=test_employee_second,
            title='Заявка 2'
        )
        
        client = auth_client_factory(test_staff_user)
        response = client.get(self.url)
        
        assert response.status_code == 200
        ids = [r['id'] for r in response.data['results']]
        
        # Должен видеть обе
        assert req1.id in ids
        assert req2.id in ids
