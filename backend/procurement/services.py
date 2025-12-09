"""
Сервисы для модуля закупок и инвентаря.
"""
import io
import os
from typing import Optional

import qrcode
from django.conf import settings
from django.core.files.base import ContentFile
from django.db import transaction
from django.utils import timezone


class InventoryNumberGenerator:
    """Генератор инвентарных номеров."""
    
    PREFIX = 'INV'
    
    @classmethod
    def generate(cls, year: Optional[int] = None) -> str:
        """
        Генерирует уникальный инвентарный номер.
        
        Формат: INV-YYYY-NNNN
        Например: INV-2025-0001, INV-2025-0002
        """
        from .models import Equipment
        
        if year is None:
            year = timezone.now().year
        
        # Находим последний номер за этот год
        prefix = f'{cls.PREFIX}-{year}-'
        last_equipment = Equipment.objects.filter(
            inventory_number__startswith=prefix
        ).order_by('-inventory_number').first()
        
        if last_equipment:
            # Извлекаем номер из последнего инвентарного номера
            try:
                last_num = int(last_equipment.inventory_number.split('-')[-1])
            except (ValueError, IndexError):
                last_num = 0
        else:
            last_num = 0
        
        new_num = last_num + 1
        return f'{cls.PREFIX}-{year}-{new_num:04d}'
    
    @classmethod
    def validate(cls, inventory_number: str) -> bool:
        """
        Проверяет формат инвентарного номера.
        
        Returns:
            True если формат верный, False иначе
        """
        parts = inventory_number.split('-')
        if len(parts) != 3:
            return False
        
        prefix, year_str, num_str = parts
        
        if prefix != cls.PREFIX:
            return False
        
        try:
            year = int(year_str)
            if year < 2000 or year > 2100:
                return False
        except ValueError:
            return False
        
        try:
            num = int(num_str)
            if num < 1:
                return False
        except ValueError:
            return False
        
        return True


class QRCodeGenerator:
    """Генератор QR-кодов для оборудования."""
    
    QR_CODE_DIR = 'qr_codes'
    
    @classmethod
    def generate_for_equipment(cls, equipment) -> ContentFile:
        """
        Генерирует QR-код для оборудования.
        
        QR содержит URL на страницу оборудования и основные данные.
        
        Returns:
            ContentFile с PNG изображением QR-кода
        """
        # Данные для QR-кода
        data = cls._build_qr_data(equipment)
        
        # Генерируем QR-код
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=10,
            border=4,
        )
        qr.add_data(data)
        qr.make(fit=True)
        
        # Создаём изображение
        img = qr.make_image(fill_color="black", back_color="white")
        
        # Сохраняем в буфер
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        buffer.seek(0)
        
        filename = f'{equipment.inventory_number}.png'
        return ContentFile(buffer.read(), name=filename)
    
    @classmethod
    def _build_qr_data(cls, equipment) -> str:
        """
        Формирует данные для QR-кода.
        
        Формат: URL с параметрами для быстрого доступа.
        """
        # Формируем URL на страницу оборудования
        base_url = getattr(settings, 'SITE_URL', 'http://localhost:8000')
        equipment_url = f'{base_url}/procurement/equipment/{equipment.id}/'
        
        # Можно также добавить vCard или JSON формат
        # Но URL проще для сканирования
        return equipment_url
    
    @classmethod
    def get_qr_code_path(cls, inventory_number: str) -> str:
        """
        Возвращает путь к файлу QR-кода.
        """
        return os.path.join(cls.QR_CODE_DIR, f'{inventory_number}.png')


class EquipmentService:
    """Сервис для операций с оборудованием."""
    
    @classmethod
    @transaction.atomic
    def create_equipment(
        cls,
        name: str,
        category,
        department,
        purchase_date,
        purchase_cost,
        **kwargs
    ):
        """
        Создаёт новое оборудование с авто-генерацией инвентарного номера.
        """
        from .models import Equipment
        
        # Генерируем инвентарный номер если не указан
        if 'inventory_number' not in kwargs or not kwargs['inventory_number']:
            kwargs['inventory_number'] = InventoryNumberGenerator.generate()
        
        equipment = Equipment.objects.create(
            name=name,
            category=category,
            department=department,
            purchase_date=purchase_date,
            purchase_cost=purchase_cost,
            **kwargs
        )
        
        return equipment
    
    @classmethod
    @transaction.atomic
    def assign_to_person(
        cls,
        equipment,
        person,
        location: Optional[str] = None
    ):
        """
        Назначает оборудование ответственному лицу.
        """
        from .constants import EquipmentStatus
        from .models import EquipmentTransferLog
        
        old_person = equipment.responsible_person
        old_location = equipment.location
        
        equipment.responsible_person = person
        equipment.status = EquipmentStatus.IN_USE
        if location:
            equipment.location = location
        equipment.save()
        
        # Логируем передачу
        EquipmentTransferLog.objects.create(
            equipment=equipment,
            from_person=old_person,
            to_person=person,
            from_location=old_location,
            to_location=location or equipment.location,
            transfer_type='assignment',
        )
        
        return equipment
    
    @classmethod
    @transaction.atomic
    def transfer(
        cls,
        equipment,
        to_department,
        to_person=None,
        to_location: Optional[str] = None,
        reason: str = ''
    ):
        """
        Перемещает оборудование в другой отдел.
        """
        from .models import EquipmentTransferLog
        
        old_department = equipment.department
        old_person = equipment.responsible_person
        old_location = equipment.location
        
        equipment.department = to_department
        equipment.responsible_person = to_person
        if to_location:
            equipment.location = to_location
        equipment.save()
        
        # Логируем передачу
        EquipmentTransferLog.objects.create(
            equipment=equipment,
            from_department=old_department,
            to_department=to_department,
            from_person=old_person,
            to_person=to_person,
            from_location=old_location,
            to_location=to_location or '',
            transfer_type='transfer',
            reason=reason,
        )
        
        return equipment
    
    @classmethod
    @transaction.atomic
    def write_off(cls, equipment, reason: str):
        """
        Списывает оборудование.
        """
        from .constants import EquipmentStatus
        
        equipment.status = EquipmentStatus.WRITTEN_OFF
        equipment.notes = (
            f'{equipment.notes}\n\n'
            f'[{timezone.now().strftime("%Y-%m-%d")}] Списано: {reason}'
        ).strip()
        equipment.save()
        
        return equipment
    
    @classmethod
    @transaction.atomic
    def add_maintenance_record(
        cls,
        equipment,
        maintenance_type: str,
        description: str,
        performed_by,
        cost=None,
        date=None
    ):
        """
        Добавляет запись о техническом обслуживании.
        """
        from decimal import Decimal
        from .models import MaintenanceRecord
        from .constants import EquipmentStatus
        
        if date is None:
            date = timezone.now().date()
        
        if cost is None:
            cost = Decimal('0.00')
        
        record = MaintenanceRecord.objects.create(
            equipment=equipment,
            date=date,
            type=maintenance_type,
            description=description,
            cost=cost,
            performed_by=performed_by,
        )
        
        # Если на ремонте - обновляем статус
        if maintenance_type == 'repair':
            equipment.status = EquipmentStatus.IN_REPAIR
            equipment.save()
        
        return record
