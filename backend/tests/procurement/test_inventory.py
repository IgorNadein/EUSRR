"""
Тесты для Inventory - transfer, write_off, QR-коды, инвентарные номера.
"""
import pytest
from rest_framework import status

from procurement.models import (
    Equipment,
    EquipmentCategory,
    EquipmentTransferLog,
    MaintenanceRecord,
)
from procurement.constants import EquipmentStatus
from procurement.services import InventoryNumberGenerator, QRCodeGenerator


@pytest.mark.django_db
class TestInventoryNumberGenerator:
    """Тесты для генератора инвентарных номеров."""

    @pytest.fixture(autouse=True)
    def setup(self, department_factory, user_factory, link_factory):
        """Настройка тестовых данных."""
        self.department = department_factory(name='IT Inventory Test')
        self.user = user_factory(staff=True,
            email='inventory_user@test.com',
            first_name='Test',
            last_name='Inventory',
        )
        link_factory(self.user, self.department, is_active=True)
        self.category = EquipmentCategory.objects.create(
            name='Computers',
            description='Компьютеры и ноутбуки',
        )

    def test_generate_first_number(self):
        """Тест: генерация первого инвентарного номера за год."""
        from django.utils import timezone
        year = timezone.now().year
        
        number = InventoryNumberGenerator.generate()
        
        assert number == f'INV-{year}-0001'

    def test_generate_sequential_numbers(self):
        """Тест: последовательная генерация номеров."""
        from django.utils import timezone
        year = timezone.now().year
        
        # Создаём оборудование с первым номером
        Equipment.objects.create(
            name='Laptop 1',
            inventory_number=f'INV-{year}-0005',
            category=self.category,
            department=self.department,
            responsible_person=self.user,
            status=EquipmentStatus.IN_USE,
            purchase_date='2025-01-01',
            purchase_cost='10000.00',
        )
        
        number = InventoryNumberGenerator.generate()
        
        assert number == f'INV-{year}-0006'

    def test_validate_correct_format(self):
        """Тест: валидация правильного формата."""
        assert InventoryNumberGenerator.validate('INV-2025-0001') is True
        assert InventoryNumberGenerator.validate('INV-2024-9999') is True

    def test_validate_incorrect_format(self):
        """Тест: валидация неправильного формата."""
        assert InventoryNumberGenerator.validate('INV-2025') is False
        assert InventoryNumberGenerator.validate('ABC-2025-0001') is False
        assert InventoryNumberGenerator.validate('') is False


@pytest.mark.django_db
class TestQRCodeGenerator:
    """Тесты для генератора QR-кодов."""

    @pytest.fixture(autouse=True)
    def setup(self, department_factory, user_factory, link_factory):
        """Настройка тестовых данных."""
        self.department = department_factory(name='IT QR Test')
        self.user = user_factory(staff=True,
            email='qr_user@test.com',
            first_name='Test',
            last_name='QR',
        )
        link_factory(self.user, self.department, is_active=True)
        self.category = EquipmentCategory.objects.create(
            name='Monitors',
            description='Мониторы',
        )
        self.equipment = Equipment.objects.create(
            name='Monitor Dell 27',
            inventory_number='INV-2025-0100',
            category=self.category,
            department=self.department,
            responsible_person=self.user,
            status=EquipmentStatus.IN_USE,
            purchase_date='2025-01-01',
            purchase_cost='10000.00',
        )

    def test_generate_qr_code(self):
        """Тест: генерация QR-кода для оборудования."""
        qr_file = QRCodeGenerator.generate_for_equipment(self.equipment)
        
        assert qr_file is not None
        assert qr_file.name.endswith('.png')
        # Файл должен содержать PNG данные
        content = qr_file.read()
        assert len(content) > 0
        # PNG начинается с signature
        assert content[:4] == b'\x89PNG'

    def test_qr_code_path(self):
        """Тест: путь к файлу QR-кода."""
        path = QRCodeGenerator.get_qr_code_path('INV-2025-0100')
        
        assert 'INV-2025-0100.png' in path


@pytest.mark.django_db
class TestEquipmentTransferEndpoint:
    """Тесты для /equipment/{id}/transfer/ endpoint."""

    @pytest.fixture(autouse=True)
    def setup(
        self, api_client, department_factory, user_factory, link_factory
    ):
        """Настройка тестовых данных."""
        self.client = api_client
        self.dept1 = department_factory(name='IT Dept')
        self.dept2 = department_factory(name='HR Dept')
        
        self.user1 = user_factory(staff=True,
            email='transfer_user1@test.com',
            first_name='User',
            last_name='One',
        )
        self.user2 = user_factory(
            email='transfer_user2@test.com',
            first_name='User',
            last_name='Two',
        )
        link_factory(self.user1, self.dept1, is_active=True)
        link_factory(self.user2, self.dept2, is_active=True)
        
        self.category = EquipmentCategory.objects.create(
            name='Laptops',
            description='Ноутбуки',
        )
        self.equipment = Equipment.objects.create(
            name='MacBook Pro',
            inventory_number='INV-2025-0200',
            category=self.category,
            department=self.dept1,
            responsible_person=self.user1,
            status=EquipmentStatus.IN_USE,
            purchase_date='2025-01-01',
            purchase_cost='10000.00',
        )

    def test_transfer_to_another_department(self):
        """Тест: перевод оборудования в другой отдел."""
        self.client.force_authenticate(user=self.user1)
        
        response = self.client.post(
            f'/api/v1/procurement/equipment/{self.equipment.id}/transfer/',
            {
                'to_department': self.dept2.id,
                'reason': 'Переезд сотрудника',
            }
        )
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['status'] == 'transferred'
        
        # Проверяем обновление оборудования
        self.equipment.refresh_from_db()
        assert self.equipment.department == self.dept2
        
        # Проверяем лог перевода
        log = EquipmentTransferLog.objects.filter(
            equipment=self.equipment
        ).first()
        assert log is not None
        assert log.from_department == self.dept1
        assert log.to_department == self.dept2
        assert log.reason == 'Переезд сотрудника'

    def test_transfer_to_another_person(self):
        """Тест: перевод оборудования другому пользователю."""
        self.client.force_authenticate(user=self.user1)
        
        response = self.client.post(
            f'/api/v1/procurement/equipment/{self.equipment.id}/transfer/',
            {
                'to_person': self.user2.id,
                'reason': 'Смена ответственного',
            }
        )
        
        assert response.status_code == status.HTTP_200_OK
        
        self.equipment.refresh_from_db()
        assert self.equipment.responsible_person == self.user2

    def test_transfer_requires_target(self):
        """Тест: нужно указать отдел или пользователя."""
        self.client.force_authenticate(user=self.user1)
        
        response = self.client.post(
            f'/api/v1/procurement/equipment/{self.equipment.id}/transfer/',
            {'reason': 'Без цели'},
        )
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
class TestEquipmentWriteOffEndpoint:
    """Тесты для /equipment/{id}/write_off/ endpoint."""

    @pytest.fixture(autouse=True)
    def setup(
        self, api_client, department_factory, user_factory, link_factory
    ):
        """Настройка тестовых данных."""
        self.client = api_client
        self.department = department_factory(name='IT WriteOff')
        self.user = user_factory(staff=True,
            email='writeoff_user@test.com',
            first_name='Test',
            last_name='WriteOff',
        )
        link_factory(self.user, self.department, is_active=True)
        
        self.category = EquipmentCategory.objects.create(
            name='Printers',
            description='Принтеры',
        )
        self.equipment = Equipment.objects.create(
            name='HP LaserJet',
            inventory_number='INV-2025-0300',
            category=self.category,
            department=self.department,
            responsible_person=self.user,
            status=EquipmentStatus.IN_USE,
            purchase_date='2025-01-01',
            purchase_cost='10000.00',
        )

    def test_write_off_equipment(self):
        """Тест: списание оборудования."""
        self.client.force_authenticate(user=self.user)
        
        response = self.client.post(
            f'/api/v1/procurement/equipment/{self.equipment.id}/write_off/',
            {'reason': 'Износ'}
        )
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['status'] == 'written_off'
        
        self.equipment.refresh_from_db()
        assert self.equipment.status == EquipmentStatus.RETIRED
        assert 'Износ' in self.equipment.notes

    def test_cannot_write_off_twice(self):
        """Тест: нельзя списать уже списанное оборудование."""
        self.equipment.status = EquipmentStatus.RETIRED
        self.equipment.save()
        
        self.client.force_authenticate(user=self.user)
        
        response = self.client.post(
            f'/api/v1/procurement/equipment/{self.equipment.id}/write_off/',
            {'reason': 'Повторно'}
        )
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
class TestEquipmentMaintenanceEndpoint:
    """Тесты для /equipment/{id}/add_maintenance/ endpoint."""

    @pytest.fixture(autouse=True)
    def setup(
        self, api_client, department_factory, user_factory, link_factory
    ):
        """Настройка тестовых данных."""
        self.client = api_client
        self.department = department_factory(name='IT Maintenance')
        self.user = user_factory(staff=True,
            email='maintenance_user@test.com',
            first_name='Test',
            last_name='Maintenance',
        )
        link_factory(self.user, self.department, is_active=True)
        
        self.category = EquipmentCategory.objects.create(
            name='Servers',
            description='Серверы',
        )
        self.equipment = Equipment.objects.create(
            name='Dell PowerEdge',
            inventory_number='INV-2025-0400',
            category=self.category,
            department=self.department,
            responsible_person=self.user,
            status=EquipmentStatus.IN_USE,
            purchase_date='2025-01-01',
            purchase_cost='10000.00',
        )

    def test_add_maintenance_record(self):
        """Тест: добавление записи об обслуживании."""
        self.client.force_authenticate(user=self.user)
        
        response = self.client.post(
            f'/api/v1/procurement/equipment/{self.equipment.id}/add_maintenance/',
            {
                'type': 'repair',
                'description': 'Замена блока питания',
                'cost': '5000.00',
            }
        )
        
        assert response.status_code == status.HTTP_201_CREATED
        assert 'maintenance_id' in response.data
        
        # Проверяем создание записи
        record = MaintenanceRecord.objects.get(id=response.data['maintenance_id'])
        assert record.equipment == self.equipment
        assert record.description == 'Замена блока питания'
        assert record.performed_by == self.user


@pytest.mark.django_db
class TestEquipmentQRCodeEndpoint:
    """Тесты для /equipment/{id}/qr_code/ endpoint."""

    @pytest.fixture(autouse=True)
    def setup(
        self, api_client, department_factory, user_factory, link_factory
    ):
        """Настройка тестовых данных."""
        self.client = api_client
        self.department = department_factory(name='IT QR Code')
        self.user = user_factory(staff=True,
            email='qrcode_user@test.com',
            first_name='Test',
            last_name='QRCode',
        )
        link_factory(self.user, self.department, is_active=True)
        
        self.category = EquipmentCategory.objects.create(
            name='Networking',
            description='Сетевое оборудование',
        )
        self.equipment = Equipment.objects.create(
            name='Cisco Router',
            inventory_number='INV-2025-0500',
            category=self.category,
            department=self.department,
            responsible_person=self.user,
            status=EquipmentStatus.IN_USE,
            purchase_date='2025-01-01',
            purchase_cost='10000.00',
        )

    def test_get_qr_code(self):
        """Тест: получение QR-кода для оборудования."""
        self.client.force_authenticate(user=self.user)
        
        response = self.client.get(
            f'/api/v1/procurement/equipment/{self.equipment.id}/qr_code/'
        )
        
        assert response.status_code == status.HTTP_200_OK
        assert response['Content-Type'] == 'image/png'
        # PNG signature
        assert response.content[:4] == b'\x89PNG'


@pytest.mark.django_db
class TestEquipmentTransferHistoryEndpoint:
    """Тесты для /equipment/{id}/transfer_history/ endpoint."""

    @pytest.fixture(autouse=True)
    def setup(
        self, api_client, department_factory, user_factory, link_factory
    ):
        """Настройка тестовых данных."""
        self.client = api_client
        self.dept1 = department_factory(name='IT History 1')
        self.dept2 = department_factory(name='IT History 2')
        
        self.user1 = user_factory(staff=True,
            email='history_user1@test.com',
            first_name='User',
            last_name='History1',
        )
        self.user2 = user_factory(
            email='history_user2@test.com',
            first_name='User',
            last_name='History2',
        )
        link_factory(self.user1, self.dept1, is_active=True)
        
        self.category = EquipmentCategory.objects.create(
            name='Phones',
            description='Телефоны',
        )
        self.equipment = Equipment.objects.create(
            name='iPhone 15',
            inventory_number='INV-2025-0600',
            category=self.category,
            department=self.dept1,
            responsible_person=self.user1,
            status=EquipmentStatus.IN_USE,
            purchase_date='2025-01-01',
            purchase_cost='10000.00',
        )
        
        # Создаём историю переводов
        EquipmentTransferLog.objects.create(
            equipment=self.equipment,
            from_department=self.dept1,
            to_department=self.dept2,
            from_person=self.user1,
            to_person=self.user2,
            reason='Первый перевод',
            created_by=self.user1,
        )

    def test_get_transfer_history(self):
        """Тест: получение истории переводов."""
        self.client.force_authenticate(user=self.user1)
        
        response = self.client.get(
            f'/api/v1/procurement/equipment/{self.equipment.id}/transfer_history/'
        )
        
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1
        assert response.data[0]['reason'] == 'Первый перевод'
        assert 'from_department' in response.data[0]
        assert 'to_department' in response.data[0]
