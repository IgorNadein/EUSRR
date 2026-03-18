"""Extended employees views for API v2."""
from api.v1.employees.views.roles import DepartmentRoleViewSet as V1DepartmentRoleViewSet
from api.v1.employees.views.actions import EmployeeActionViewSet as V1EmployeeActionViewSet
from api.v1.employees.views.groups import GroupViewSet as V1GroupViewSet
from api.v1.employees.views.positions import PositionViewSet as V1PositionViewSet
from api.v1.employees.views.skills import SkillViewSet as V1SkillViewSet


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
