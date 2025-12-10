# backend/procurement/models.py
"""
Модели для модуля закупок и инвентаря.

Основные сущности:
- ProcurementRequest: заявка на закупку
- ProcurementItem: позиция в заявке
- Approval: запись о согласовании
- Equipment: единица оборудования/инвентаря
- EquipmentCategory: категория оборудования
- MaintenanceRecord: запись об обслуживании
- Budget: бюджет отдела
- Supplier: поставщик
"""

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone
from employees.models import Department

from .constants import (
    APPROVAL_THRESHOLD_HIGH,
    APPROVAL_THRESHOLD_LOW,
    ApprovalRole,
    ApprovalStatus,
    EquipmentStatus,
    MaintenanceType,
    ProcurementStatus,
    UrgencyLevel,
)

User = get_user_model()


class ProcurementRequest(models.Model):
    """Заявка на закупку.
    
    Статусы: DRAFT → PENDING → APPROVED → IN_PROGRESS → COMPLETED
    Альтернативные переходы: → REJECTED, → CANCELLED
    """
    
    title = models.CharField(
        'Название',
        max_length=255,
        help_text='Краткое название заявки'
    )
    description = models.TextField(
        'Описание',
        help_text='Подробное описание и обоснование необходимости закупки'
    )
    department = models.ForeignKey(
        Department,
        on_delete=models.PROTECT,
        related_name='procurement_requests',
        verbose_name='Отдел'
    )
    requestor = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='procurement_requests',
        verbose_name='Заявитель'
    )
    status = models.CharField(
        'Статус',
        max_length=20,
        choices=ProcurementStatus.choices,
        default=ProcurementStatus.DRAFT
    )
    urgency = models.CharField(
        'Срочность',
        max_length=20,
        choices=UrgencyLevel.choices,
        default=UrgencyLevel.MEDIUM
    )
    estimated_cost = models.DecimalField(
        'Предполагаемая стоимость',
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    actual_cost = models.DecimalField(
        'Фактическая стоимость',
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    
    # Даты
    created_at = models.DateTimeField(
        'Создано',
        auto_now_add=True
    )
    updated_at = models.DateTimeField(
        'Обновлено',
        auto_now=True
    )
    submitted_at = models.DateTimeField(
        'Отправлено на согласование',
        null=True,
        blank=True
    )
    completed_at = models.DateTimeField(
        'Завершено',
        null=True,
        blank=True
    )
    
    class Meta:
        verbose_name = 'Заявка на закупку'
        verbose_name_plural = 'Заявки на закупку'
        ordering = ['-created_at']
        permissions = [
            ('approve_procurementrequest', 'Can approve procurement requests'),
            ('view_all_requests', 'Can view all department requests'),
            ('execute_procurement', 'Can execute approved requests'),
        ]
    
    def __str__(self):
        return f"#{self.pk} {self.title}"
    
    def get_required_approvals(self):
        """Возвращает список необходимых ролей для согласования.
        
        Логика:
        - < 10,000₽: только руководитель отдела
        - 10,000 - 100,000₽: руководитель + финансовый менеджер
        - > 100,000₽: руководитель + финансы + директор
        """
        cost = self.estimated_cost or Decimal('0')
        
        if cost < APPROVAL_THRESHOLD_LOW:
            return [ApprovalRole.DEPARTMENT_HEAD]
        elif cost < APPROVAL_THRESHOLD_HIGH:
            return [
                ApprovalRole.DEPARTMENT_HEAD,
                ApprovalRole.FINANCE_MANAGER
            ]
        else:
            return [
                ApprovalRole.DEPARTMENT_HEAD,
                ApprovalRole.FINANCE_MANAGER,
                ApprovalRole.DIRECTOR
            ]
    
    def check_budget_available(self):
        """Проверяет наличие бюджета в отделе.
        
        Returns:
            tuple: (bool, Decimal) - (доступно ли, остаток бюджета)
        """
        # Определяем текущий квартал
        now = timezone.now()
        quarter = (now.month - 1) // 3 + 1
        
        try:
            budget = Budget.objects.get(
                department=self.department,
                year=now.year,
                quarter=quarter
            )
            remaining = budget.remaining_amount
            return (remaining >= self.estimated_cost, remaining)
        except Budget.DoesNotExist:
            return (False, Decimal('0'))
    
    @property
    def items_count(self):
        """Количество позиций в заявке."""
        return self.items.count()
    
    @property
    def is_editable(self):
        """Можно ли редактировать заявку."""
        return self.status == ProcurementStatus.DRAFT


class ProcurementItem(models.Model):
    """Позиция в заявке на закупку."""
    
    request = models.ForeignKey(
        ProcurementRequest,
        on_delete=models.CASCADE,
        related_name='items',
        verbose_name='Заявка'
    )
    name = models.CharField(
        'Название',
        max_length=255,
        help_text='Название товара или услуги'
    )
    description = models.TextField(
        'Описание',
        blank=True,
        help_text='Подробное описание, технические характеристики'
    )
    quantity = models.PositiveIntegerField(
        'Количество',
        default=1,
        validators=[MinValueValidator(1)]
    )
    unit = models.CharField(
        'Единица измерения',
        max_length=50,
        default='шт',
        help_text='Например: шт, кг, л, упак, м'
    )
    estimated_unit_price = models.DecimalField(
        'Цена за единицу',
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    supplier_info = models.TextField(
        'Информация о поставщике',
        blank=True,
        help_text='Ссылки на товар, контакты поставщика'
    )
    equipment = models.OneToOneField(
        'Equipment',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='procurement_item',
        verbose_name='Оборудование',
        help_text='Связь с оборудованием после закупки'
    )
    created_at = models.DateTimeField('Создано', auto_now_add=True)
    
    class Meta:
        verbose_name = 'Позиция заявки'
        verbose_name_plural = 'Позиции заявок'
        ordering = ['id']
    
    def __str__(self):
        return f"{self.name} ({self.quantity} {self.unit})"
    
    @property
    def total_price(self):
        """Общая стоимость позиции."""
        return self.estimated_unit_price * self.quantity


class Approval(models.Model):
    """Запись о согласовании заявки."""
    
    request = models.ForeignKey(
        ProcurementRequest,
        on_delete=models.CASCADE,
        related_name='approvals',
        verbose_name='Заявка'
    )
    approver = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='procurement_approvals',
        verbose_name='Согласующий'
    )
    role = models.CharField(
        'Роль',
        max_length=20,
        choices=ApprovalRole.choices,
        help_text='Роль согласующего в процессе'
    )
    status = models.CharField(
        'Статус',
        max_length=20,
        choices=ApprovalStatus.choices,
        default=ApprovalStatus.PENDING
    )
    comment = models.TextField(
        'Комментарий',
        blank=True
    )
    created_at = models.DateTimeField('Создано', auto_now_add=True)
    updated_at = models.DateTimeField('Обновлено', auto_now=True)
    
    class Meta:
        verbose_name = 'Согласование'
        verbose_name_plural = 'Согласования'
        ordering = ['created_at']
        unique_together = [('request', 'role')]
    
    def __str__(self):
        return (
            f"{self.get_role_display()} - "
            f"{self.get_status_display()}"
        )


class EquipmentCategory(models.Model):
    """Категория оборудования (иерархическая)."""
    
    name = models.CharField(
        'Название',
        max_length=100,
        unique=True
    )
    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='children',
        verbose_name='Родительская категория'
    )
    description = models.TextField(
        'Описание',
        blank=True
    )
    icon = models.CharField(
        'Иконка Bootstrap',
        max_length=50,
        blank=True,
        help_text='Например: bi-laptop, bi-printer'
    )
    created_at = models.DateTimeField('Создано', auto_now_add=True)
    
    class Meta:
        verbose_name = 'Категория оборудования'
        verbose_name_plural = 'Категории оборудования'
        ordering = ['name']
    
    def __str__(self):
        if self.parent:
            return f"{self.parent.name} → {self.name}"
        return self.name
    
    @property
    def full_path(self):
        """Полный путь категории."""
        if self.parent:
            return f"{self.parent.full_path} → {self.name}"
        return self.name


class Equipment(models.Model):
    """Единица оборудования/инвентаря."""
    
    name = models.CharField(
        'Название',
        max_length=255
    )
    inventory_number = models.CharField(
        'Инвентарный номер',
        max_length=50,
        unique=True,
        help_text='Например: INV-2024-0001'
    )
    serial_number = models.CharField(
        'Серийный номер',
        max_length=100,
        blank=True,
        help_text='Серийный номер производителя'
    )
    category = models.ForeignKey(
        EquipmentCategory,
        on_delete=models.PROTECT,
        related_name='equipment',
        verbose_name='Категория'
    )
    status = models.CharField(
        'Статус',
        max_length=20,
        choices=EquipmentStatus.choices,
        default=EquipmentStatus.AVAILABLE
    )
    department = models.ForeignKey(
        Department,
        on_delete=models.PROTECT,
        related_name='equipment',
        verbose_name='Отдел'
    )
    responsible_person = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='responsible_equipment',
        verbose_name='Ответственный'
    )
    location = models.CharField(
        'Расположение',
        max_length=255,
        blank=True,
        help_text='Например: Офис 3.14, Стеллаж А-5'
    )
    purchase_date = models.DateField(
        'Дата покупки'
    )
    warranty_until = models.DateField(
        'Гарантия до',
        null=True,
        blank=True
    )
    purchase_cost = models.DecimalField(
        'Стоимость покупки',
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    notes = models.TextField(
        'Примечания',
        blank=True
    )
    created_at = models.DateTimeField('Создано', auto_now_add=True)
    updated_at = models.DateTimeField('Обновлено', auto_now=True)
    
    class Meta:
        verbose_name = 'Оборудование'
        verbose_name_plural = 'Оборудование'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.inventory_number} - {self.name}"
    
    @property
    def is_under_warranty(self):
        """Находится ли под гарантией."""
        if not self.warranty_until:
            return False
        return timezone.now().date() <= self.warranty_until


class MaintenanceRecord(models.Model):
    """Запись о техническом обслуживании оборудования."""
    
    equipment = models.ForeignKey(
        Equipment,
        on_delete=models.CASCADE,
        related_name='maintenance_history',
        verbose_name='Оборудование'
    )
    date = models.DateField(
        'Дата обслуживания'
    )
    type = models.CharField(
        'Тип обслуживания',
        max_length=20,
        choices=MaintenanceType.choices
    )
    description = models.TextField(
        'Описание',
        help_text='Что было сделано'
    )
    cost = models.DecimalField(
        'Стоимость',
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    performed_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='performed_maintenance',
        verbose_name='Выполнил'
    )
    next_maintenance_date = models.DateField(
        'Следующее ТО',
        null=True,
        blank=True
    )
    created_at = models.DateTimeField('Создано', auto_now_add=True)
    
    class Meta:
        verbose_name = 'Запись обслуживания'
        verbose_name_plural = 'Записи обслуживания'
        ordering = ['-date']
    
    def __str__(self):
        return (
            f"{self.equipment.inventory_number} - "
            f"{self.get_type_display()} ({self.date})"
        )


class EquipmentTransferLog(models.Model):
    """Лог передачи/перемещения оборудования."""
    
    TRANSFER_TYPES = [
        ('assignment', 'Назначение ответственного'),
        ('transfer', 'Перемещение'),
        ('return', 'Возврат'),
    ]
    
    equipment = models.ForeignKey(
        Equipment,
        on_delete=models.CASCADE,
        related_name='transfer_logs',
        verbose_name='Оборудование'
    )
    from_department = models.ForeignKey(
        Department,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='transfers_out',
        verbose_name='Из отдела'
    )
    to_department = models.ForeignKey(
        Department,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='transfers_in',
        verbose_name='В отдел'
    )
    from_person = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='equipment_given',
        verbose_name='От кого'
    )
    to_person = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='equipment_received',
        verbose_name='Кому'
    )
    from_location = models.CharField(
        'Откуда',
        max_length=255,
        blank=True
    )
    to_location = models.CharField(
        'Куда',
        max_length=255,
        blank=True
    )
    transfer_type = models.CharField(
        'Тип передачи',
        max_length=20,
        choices=TRANSFER_TYPES,
        default='transfer'
    )
    reason = models.TextField(
        'Причина/комментарий',
        blank=True
    )
    created_at = models.DateTimeField('Дата передачи', auto_now_add=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='transfers_created',
        verbose_name='Кто оформил'
    )
    
    class Meta:
        verbose_name = 'Лог передачи'
        verbose_name_plural = 'Логи передач'
        ordering = ['-created_at']
    
    def __str__(self):
        return (
            f"{self.equipment.inventory_number}: "
            f"{self.from_person or 'Склад'} → {self.to_person or 'Склад'}"
        )


class Budget(models.Model):
    """Бюджет отдела на квартал."""
    
    department = models.ForeignKey(
        Department,
        on_delete=models.CASCADE,
        related_name='budgets',
        verbose_name='Отдел'
    )
    year = models.PositiveIntegerField(
        'Год',
        help_text='Например: 2025'
    )
    quarter = models.PositiveIntegerField(
        'Квартал',
        choices=[(1, '1 квартал'), (2, '2 квартал'),
                 (3, '3 квартал'), (4, '4 квартал')]
    )
    allocated_amount = models.DecimalField(
        'Выделено',
        max_digits=14,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    spent_amount = models.DecimalField(
        'Потрачено',
        max_digits=14,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    created_at = models.DateTimeField('Создано', auto_now_add=True)
    updated_at = models.DateTimeField('Обновлено', auto_now=True)
    
    class Meta:
        verbose_name = 'Бюджет'
        verbose_name_plural = 'Бюджеты'
        ordering = ['-year', '-quarter']
        unique_together = [('department', 'year', 'quarter')]
    
    def __str__(self):
        return (
            f"{self.department.name} - "
            f"{self.year} Q{self.quarter}"
        )
    
    @property
    def remaining_amount(self):
        """Остаток бюджета."""
        allocated = self.allocated_amount or Decimal('0.00')
        return allocated - self.spent_amount
    
    @property
    def reserved_amount(self):
        """Сумма зарезервированная pending заявками."""
        from django.db.models import Sum
        pending_sum = self.department.procurement_requests.filter(
            status=ProcurementStatus.PENDING,
            created_at__year=self.year,
            created_at__month__in=self._quarter_months()
        ).aggregate(total=Sum('estimated_cost'))['total']
        return pending_sum or Decimal('0.00')
    
    @property
    def available_amount(self):
        """Доступный бюджет (с учётом резерва)."""
        return self.remaining_amount - self.reserved_amount
    
    def _quarter_months(self):
        """Получить месяцы квартала."""
        return {
            1: [1, 2, 3],
            2: [4, 5, 6],
            3: [7, 8, 9],
            4: [10, 11, 12],
        }[self.quarter]
    
    @property
    def utilization_percentage(self):
        """Процент использования бюджета."""
        allocated = self.allocated_amount or Decimal('0.00')
        if allocated == 0:
            return Decimal('0.00')
        return (
            self.spent_amount / allocated * 100
        ).quantize(Decimal('0.01'))
    
    def can_spend(self, amount):
        """Проверка возможности потратить сумму."""
        return self.remaining_amount >= amount


class Supplier(models.Model):
    """Поставщик товаров/услуг."""
    
    name = models.CharField(
        'Название',
        max_length=255
    )
    contact_person = models.CharField(
        'Контактное лицо',
        max_length=255,
        blank=True
    )
    phone = models.CharField(
        'Телефон',
        max_length=50,
        blank=True
    )
    email = models.EmailField(
        'Email',
        blank=True
    )
    address = models.TextField(
        'Адрес',
        blank=True
    )
    website = models.URLField(
        'Веб-сайт',
        blank=True
    )
    inn = models.CharField(
        'ИНН',
        max_length=12,
        blank=True,
        help_text='ИНН организации (10 или 12 цифр)'
    )
    rating = models.DecimalField(
        'Рейтинг',
        max_digits=3,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    is_active = models.BooleanField(
        'Активен',
        default=True
    )
    notes = models.TextField(
        'Примечания',
        blank=True
    )
    created_at = models.DateTimeField('Создано', auto_now_add=True)
    updated_at = models.DateTimeField('Обновлено', auto_now=True)
    
    class Meta:
        verbose_name = 'Поставщик'
        verbose_name_plural = 'Поставщики'
        ordering = ['name']
    
    def __str__(self):
        return self.name
