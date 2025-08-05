from rest_framework import serializers
from employees.models import Employee, Department, EmployeeAction, EmployeePosition, Absence, Skill, Education


class SkillSerializer(serializers.ModelSerializer):
    class Meta:
        model = Skill
        fields = ['id', 'name']


class DepartmentSerializer(serializers.ModelSerializer):
    head = serializers.StringRelatedField()

    class Meta:
        model = Department
        fields = ['id', 'name', 'description', 'head', 'created_at']


class EmployeeActionSerializer(serializers.ModelSerializer):
    employee = serializers.StringRelatedField(read_only=True)

    class Meta:
        model = EmployeeAction
        fields = ['id', 'employee', 'action', 'date', 'comment', 'extra']


class EmployeePositionSerializer(serializers.ModelSerializer):
    department = DepartmentSerializer(read_only=True)
    employee = serializers.StringRelatedField(read_only=True)

    class Meta:
        model = EmployeePosition
        fields = ['id', 'employee', 'department',
                  'title', 'date_from', 'date_to', 'is_active']


class AbsenceSerializer(serializers.ModelSerializer):
    employee = serializers.StringRelatedField(read_only=True)

    class Meta:
        model = Absence
        fields = ['id', 'employee', 'type',
                  'date_from', 'date_to', 'comment', 'status']


class EducationSerializer(serializers.ModelSerializer):
    employee = serializers.StringRelatedField(read_only=True)

    class Meta:
        model = Education
        fields = ['id', 'employee', 'institution', 'degree', 'graduation_year']


class EmployeeSerializer(serializers.ModelSerializer):
    skills = SkillSerializer(many=True, read_only=True)
    positions = EmployeePositionSerializer(many=True, read_only=True)
    actions = EmployeeActionSerializer(many=True, read_only=True)
    absences = AbsenceSerializer(many=True, read_only=True)
    educations = EducationSerializer(many=True, read_only=True)
    department = serializers.SerializerMethodField()
    avatar = serializers.SerializerMethodField()

    class Meta:
        model = Employee
        fields = [
            'id', 'last_name', 'first_name', 'patronymic', 'gender', 'avatar',
            'phone_number', 'email', 'telegram', 'whatsapp', 'wechat',
            'birth_date', 'skills', 'positions', 'actions', 'absences', 'educations',
            'employment_status', 'is_actually_active', 'created_at', 'updated_at', 'department'
        ]

    def get_department(self, obj):
        active_position = obj.positions.filter(date_to__isnull=True).first()
        if active_position:
            return DepartmentSerializer(active_position.department).data
        return None

    def get_avatar(self, obj):
        request = self.context.get('request')
        if obj.avatar and request:
            return request.build_absolute_uri(obj.avatar.url)
        return None
