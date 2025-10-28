"""
Интеграционные тесты для LDAP модуля.

Эти тесты проверяют взаимодействие между сервисами
и полные сценарии работы с пользователями, отделами и должностями.
"""

import pytest
from unittest.mock import Mock, patch

from employees.models import Employee, Department, Position
from employees.ldap.services.user_service import UserService
from employees.ldap.services.department_service import DepartmentService
from employees.ldap.services.group_service import GroupService
from employees.ldap.services.position_service import PositionService
from employees.ldap.domain.dtos import DirectoryUserDTO, DirectoryDepartmentDTO


@pytest.fixture
def all_services(
    mock_ldap_repository,
    mock_employee_repository,
    mock_sync_state_repository
):
    """Создает все сервисы для интеграционных тестов."""
    group_service = GroupService(mock_ldap_repository)
    user_service = UserService(
        mock_ldap_repository,
        mock_employee_repository,
        mock_sync_state_repository
    )
    department_service = DepartmentService(
        group_service,
        user_service
    )
    position_service = PositionService(group_service, user_service)
    
    return {
        'user': user_service,
        'department': department_service,
        'group': group_service,
        'position': position_service
    }


class TestUserLifecycle:
    """Тесты полного жизненного цикла пользователя."""
    
    @pytest.mark.django_db
    def test_full_user_lifecycle(
        self,
        mock_ldap_context,
        mock_ldap_connection,
        all_services,
        sample_user_dto
    ):
        """
        Тест полного цикла: создание → обновление → деактивация → удаление.
        """
        user_service = all_services['user']
        
        # 1. Создание пользователя
        with patch('employees.models.Employee.objects.create') as mock_create:
            mock_employee = Mock(spec=Employee)
            mock_employee.id = 1
            mock_employee.first_name = "Иван"
            mock_employee.last_name = "Иванов"
            mock_employee.is_active = True
            mock_create.return_value = mock_employee
            
            employee = user_service.create_user(sample_user_dto)
            assert employee is not None
            assert mock_ldap_connection.add.called
        
        # 2. Обновление пользователя
        sample_user_dto.email = "new_email@example.com"
        user_service.update_user(employee, sample_user_dto)
        assert mock_ldap_connection.modify.called
        
        # 3. Мягкое удаление (деактивация)
        user_service.delete_user(employee, soft=True)
        assert not employee.is_active
        
        # 4. Жесткое удаление
        mock_ldap_connection.reset_mock()
        user_service.delete_user(employee, soft=False)
        assert mock_ldap_connection.delete.called
    
    @pytest.mark.django_db
    def test_user_with_department(
        self,
        mock_ldap_context,
        mock_ldap_connection,
        all_services,
        sample_user_dto,
        sample_department_dto
    ):
        """Тест создания пользователя с привязкой к отделу."""
        user_service = all_services['user']
        department_service = all_services['department']
        
        # 1. Создаем отдел
        with patch.object(
            department_service,
            '_get_department_dn',
            return_value='OU=IT,DC=example,DC=com'
        ):
            department_service.create_department(sample_department_dto)
        
        # 2. Создаем пользователя в отделе
        with patch('employees.models.Employee.objects.create') as mock_create:
            mock_employee = Mock(spec=Employee)
            mock_employee.id = 1
            mock_create.return_value = mock_employee
            
            employee = user_service.create_user(sample_user_dto)
        
        # 3. Добавляем в отдел
        with patch('employees.models.Department.objects.first') as mock_dept:
            mock_dept.return_value = Mock(spec=Department)
            mock_dept.return_value.id = 1
            
            with patch.object(
                department_service,
                '_get_department_dn',
                return_value='OU=IT,DC=example,DC=com'
            ):
                department_service.add_member(
                    mock_dept.return_value,
                    employee
                )
        
        # Assert: проверяем вызовы LDAP операций
        assert mock_ldap_connection.add.call_count >= 2


class TestDepartmentWorkflow:
    """Тесты рабочих процессов с отделами."""
    
    @pytest.mark.django_db
    def test_department_with_members(
        self,
        mock_ldap_context,
        mock_ldap_connection,
        all_services,
        sample_department_dto,
        sample_user_dto
    ):
        """
        Тест создания отдела с сотрудниками.
        Создание отдела → добавление сотрудников → назначение руководителя.
        """
        department_service = all_services['department']
        user_service = all_services['user']
        
        # 1. Создаем отдел
        with patch.object(
            department_service,
            '_get_department_dn',
            return_value='OU=IT,DC=example,DC=com'
        ):
            department_service.create_department(sample_department_dto)
        
        # 2. Создаем сотрудников
        employees = []
        for i in range(3):
            with patch(
                'employees.models.Employee.objects.create'
            ) as mock_create:
                mock_employee = Mock(spec=Employee)
                mock_employee.id = i + 1
                mock_create.return_value = mock_employee
                
                employee = user_service.create_user(sample_user_dto)
                employees.append(employee)
        
        # 3. Добавляем сотрудников в отдел
        with patch('employees.models.Department.objects.first') as mock_dept:
            department = Mock(spec=Department)
            department.id = 1
            mock_dept.return_value = department
            
            with patch.object(
                department_service,
                '_get_department_dn',
                return_value='OU=IT,DC=example,DC=com'
            ):
                for employee in employees:
                    department_service.add_member(department, employee)
        
        # 4. Назначаем руководителя
        with patch.object(
            department_service,
            '_get_department_dn',
            return_value='OU=IT,DC=example,DC=com'
        ):
            department_service.set_head(department, employees[0])
        
        # Assert: множественные LDAP операции
        assert mock_ldap_connection.add.call_count >= 4
    
    @pytest.mark.django_db
    def test_department_restructure(
        self,
        mock_ldap_context,
        mock_ldap_connection,
        all_services,
        sample_department
    ):
        """Тест реструктуризации: перемещение сотрудников между отделами."""
        department_service = all_services['department']
        
        # Создаем 2 отдела
        dept1 = sample_department
        dept2 = Department.objects.create(
            name="HR Department",
            short_name="HR"
        )
        
        # Создаем сотрудника в первом отделе
        with patch('employees.models.Employee.objects.create') as mock_create:
            employee = Mock(spec=Employee)
            employee.id = 1
            employee.department = dept1
            mock_create.return_value = employee
        
        # Перемещаем во второй отдел
        with patch.object(
            department_service,
            '_get_department_dn',
            side_effect=[
                'OU=IT,DC=example,DC=com',
                'OU=HR,DC=example,DC=com'
            ]
        ):
            department_service.remove_member(dept1, employee)
            department_service.add_member(dept2, employee)
        
        # Assert
        assert mock_ldap_connection.modify.called


class TestPositionAssignmentFlow:
    """Тесты назначения должностей."""
    
    @pytest.mark.django_db
    def test_position_assignment_workflow(
        self,
        mock_ldap_context,
        mock_ldap_connection,
        all_services,
        sample_position,
        sample_user_dto
    ):
        """
        Тест: создание пользователя → назначение должности → синхронизация.
        """
        user_service = all_services['user']
        position_service = all_services['position']
        
        # 1. Создаем пользователя
        with patch('employees.models.Employee.objects.create') as mock_create:
            employee = Mock(spec=Employee)
            employee.id = 1
            mock_create.return_value = employee
            
            employee = user_service.create_user(sample_user_dto)
        
        # 2. Назначаем должность
        pos_dn = f'CN=POS_{sample_position.id},OU=Positions,DC=example,DC=com'
        
        with patch.object(
            position_service,
            '_ensure_position_group',
            return_value=pos_dn
        ):
            position_service.assign_position(sample_position, employee)
        
        # 3. Синхронизируем должность
        with patch.object(Employee.objects, 'filter') as mock_filter:
            mock_filter.return_value = [employee]
            
            with patch.object(
                position_service,
                '_ensure_position_group',
                return_value=pos_dn
            ):
                position_service.reconcile_position(sample_position)
        
        # Assert: проверяем операции с группами
        group_service = all_services['group']
        assert group_service.add_members.call_count >= 1
    
    @pytest.mark.django_db
    def test_position_hierarchy(
        self,
        mock_ldap_context,
        mock_ldap_connection,
        all_services
    ):
        """Тест иерархии должностей (должность в должности)."""
        position_service = all_services['position']
        
        # Создаем родительскую и дочернюю должности
        parent_pos = Position.objects.create(
            name="Senior Developer",
            description="Senior position"
        )
        child_pos = Position.objects.create(
            name="Middle Developer",
            description="Middle position",
            parent=parent_pos
        )
        
        parent_dn = f'CN=POS_{parent_pos.id},OU=Positions,DC=example,DC=com'
        child_dn = f'CN=POS_{child_pos.id},OU=Positions,DC=example,DC=com'
        
        with patch.object(
            position_service,
            '_ensure_position_group',
            side_effect=[child_dn, parent_dn]
        ):
            with patch.object(Employee.objects, 'filter') as mock_filter:
                mock_filter.return_value = []
                
                # Синхронизируем дочернюю должность
                position_service.reconcile_position(child_pos)
        
        # Assert: дочерняя группа должна быть добавлена в родительскую
        group_service = all_services['group']
        assert group_service.add_members.called


class TestComplexScenarios:
    """Тесты сложных сценариев."""
    
    @pytest.mark.django_db
    def test_bulk_user_import(
        self,
        mock_ldap_context,
        mock_ldap_connection,
        all_services
    ):
        """Тест массового импорта пользователей."""
        user_service = all_services['user']
        
        # Подготавливаем данные для 10 пользователей
        users_data = []
        for i in range(10):
            dto = DirectoryUserDTO(
                first_name=f"User{i}",
                last_name=f"Last{i}",
                email=f"user{i}@example.com",
                password="Test123456!"
            )
            users_data.append(dto)
        
        # Создаем пользователей
        created_count = 0
        for dto in users_data:
            with patch('employees.models.Employee.objects.create') as mock:
                mock_employee = Mock(spec=Employee)
                mock_employee.id = created_count + 1
                mock.return_value = mock_employee
                
                employee = user_service.create_user(dto)
                if employee:
                    created_count += 1
        
        # Assert
        assert created_count == 10
        assert mock_ldap_connection.add.call_count >= 10
    
    @pytest.mark.django_db
    def test_organization_restructure(
        self,
        mock_ldap_context,
        mock_ldap_connection,
        all_services
    ):
        """Тест полной реструктуризации организации."""
        department_service = all_services['department']
        
        # Создаем структуру отделов
        root_dept = Department.objects.create(
            name="Company",
            short_name="ROOT"
        )
        
        it_dept = Department.objects.create(
            name="IT Department",
            short_name="IT",
            parent=root_dept
        )
        
        hr_dept = Department.objects.create(
            name="HR Department",
            short_name="HR",
            parent=root_dept
        )
        
        # Mock DN генерацию
        def get_dept_dn(dept):
            if dept == root_dept:
                return 'OU=ROOT,DC=example,DC=com'
            elif dept == it_dept:
                return 'OU=IT,OU=ROOT,DC=example,DC=com'
            elif dept == hr_dept:
                return 'OU=HR,OU=ROOT,DC=example,DC=com'
            return 'DC=example,DC=com'
        
        with patch.object(
            department_service,
            '_get_department_dn',
            side_effect=get_dept_dn
        ):
            # Создаем отделы в AD
            dto = DirectoryDepartmentDTO(name="Company", parent=None)
            department_service.create_department(dto)
            
            dto = DirectoryDepartmentDTO(name="IT", parent=root_dept)
            department_service.create_department(dto)
            
            dto = DirectoryDepartmentDTO(name="HR", parent=root_dept)
            department_service.create_department(dto)
        
        # Assert: создано 3 OU и 3 группы
        assert mock_ldap_connection.add.call_count >= 6
