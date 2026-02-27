"""Serializers for Employee and Department API v2."""
from django.contrib.auth import get_user_model
from employees.models import Department, Employee, Position
from rest_framework import serializers


Employee = get_user_model()


class EmployeeBriefSerializer(serializers.ModelSerializer):
    """Краткая информация о сотруднике."""

    display_name = serializers.SerializerMethodField()
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = Employee
        fields = (
            'id',
            'first_name',
            'last_name',
            'patronymic',
            'email',
            'phone_number',
            'display_name',
            'full_name',
            'avatar',
        )
        read_only_fields = fields

    def get_display_name(self, obj) -> str:
        """Читабельное имя: ФИО -> email -> phone -> 'Сотрудник #id'"""
        parts = [obj.last_name or '',
                 obj.first_name or '', obj.patronymic or '']
        fio = ' '.join(p.strip() for p in parts if p)
        if fio:
            return fio
        if getattr(obj, 'email', None):
            return obj.email
        if getattr(obj, 'phone_number', None):
            return obj.phone_number
        return f'Сотрудник #{obj.id}'

    def get_full_name(self, obj) -> str:
        """Полное имя."""
        parts = [
            obj.last_name or '',
            obj.first_name or '',
            getattr(obj, 'patronymic', '') or '',
        ]
        return ' '.join(p.strip() for p in parts if p)


class EmployeeSerializer(serializers.ModelSerializer):
    """Employee serializer for v2 API.

    Отличия от v1:
    - Упрощенная логика (без прямой работы с LDAP)
    - LDAP синхронизация через сигналы
    """

    position = serializers.StringRelatedField(read_only=True)
    position_id = serializers.PrimaryKeyRelatedField(
        source='position',
        queryset=Position.objects.all(),
        write_only=True,
        required=False,
        allow_null=True
    )
    department = serializers.SerializerMethodField()
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = Employee
        fields = [
            'id',
            'email',
            'password',
            'first_name',
            'last_name',
            'patronymic',
            'full_name',
            'phone_number',
            'birth_date',
            'gender',
            'telegram',
            'whatsapp',
            'wechat',
            'avatar',
            'position',
            'position_id',
            'department',
            'is_active',
            'is_ldap_managed',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at',
                            'updated_at', 'is_ldap_managed', 'full_name']
        extra_kwargs = {
            'password': {'write_only': True, 'required': False},
        }

    def get_full_name(self, obj) -> str:
        """Полное имя."""
        parts = [obj.last_name or '',
                 obj.first_name or '', obj.patronymic or '']
        return ' '.join(p.strip() for p in parts if p)

    def get_department(self, obj):
        """Получить основной отдел сотрудника."""
        from employees.models import EmployeeDepartment
        dept_link = EmployeeDepartment.objects.filter(
            employee=obj,
            is_active=True
        ).select_related('department').first()

        if dept_link:
            return {
                'id': dept_link.department.id,
                'name': dept_link.department.name
            }
        return None

    def create(self, validated_data):
        """Создание сотрудника с обработкой пароля.

        Специальная логика:
        - Извлекает пароль из validated_data
        - Сохраняет его во временном атрибуте _raw_password для LDAP сигнала
        - Использует create_user() для правильной установки пароля
        - LDAP синхронизация происходит через post_save сигнал
        """
        # Извлекаем пароль из validated_data
        password = validated_data.pop('password', None)

        # Создаем пользователя
        employee = Employee(**validated_data)

        if password:
            # Сохраняем открытый пароль для LDAP сигнала
            employee._raw_password = password
            # Устанавливаем хэшированный пароль
            employee.set_password(password)

        employee.save()
        return employee


class DepartmentSerializer(serializers.ModelSerializer):
    """Сериализатор для Department API v2.

    Чтение:
    - id, name, description, head (полная информация), employees_count

    Запись:
    - name, description, head_id (FK)
    """

    head = EmployeeBriefSerializer(read_only=True)
    head_id = serializers.PrimaryKeyRelatedField(
        source='head',
        queryset=Employee.objects.all(),
        write_only=True,
        required=False,
        allow_null=True,
    )
    employees_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Department
        fields = (
            'id',
            'name',
            'description',
            'head',
            'head_id',
            'employees_count',
        )
        read_only_fields = ('id', 'employees_count')

    def validate_name(self, value):
        """Валидация имени отдела."""
        if not value or not value.strip():
            raise serializers.ValidationError(
                'Название отдела не может быть пустым')

        # Проверка уникальности (с учетом update)
        instance = self.instance
        qs = Department.objects.filter(name__iexact=value.strip())
        if instance:
            qs = qs.exclude(pk=instance.pk)

        if qs.exists():
            raise serializers.ValidationError(
                'Отдел с таким названием уже существует')

        return value.strip()

    def validate_head_id(self, value):
        """Валидация руководителя отдела."""
        if value and not value.is_active:
            raise serializers.ValidationError(
                'Руководитель должен быть активным пользователем')
        return value
