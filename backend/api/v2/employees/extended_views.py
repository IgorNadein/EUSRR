"""Extended employees views for API v2."""
from api.v1.employees.views import (
    DepartmentRoleViewSet as V1DepartmentRoleViewSet,
    EmployeeActionViewSet as V1EmployeeActionViewSet,
    GroupViewSet as V1GroupViewSet,
    PositionViewSet as V1PositionViewSet,
    SkillViewSet as V1SkillViewSet,
)


class PositionViewSet(V1PositionViewSet):
    """API v2 для должностей."""
    pass


class DepartmentRoleViewSet(V1DepartmentRoleViewSet):
    """API v2 для ролей в отделах."""
    pass


class SkillViewSet(V1SkillViewSet):
    """API v2 для навыков."""
    pass


class EmployeeActionViewSet(V1EmployeeActionViewSet):
    """API v2 для действий с сотрудниками."""
    pass


class GroupViewSet(V1GroupViewSet):
    """API v2 для групп."""
    pass
