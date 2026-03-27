"""Пакет сериализаторов employees — обратно-совместимый реэкспорт."""

from .auth import EmailSerializer, EmailVerifySerializer, RegisterSerializer
from .department import (
    AddMemberInput,
    DepartmentBriefSerializer,
    DepartmentSerializer,
    RemoveMemberInput,
    SetHeadInput,
    SetMemberRoleInput,
)
from .employee import (
    EmployeeBriefSerializer,
    EmployeeListSerializer,
    EmployeeSerializer,
    ProfilePatchSerializer,
)
from .role import DepartmentRoleSerializer, GroupSerializer
from .shared import (
    EmployeeActionSerializer,
    PositionBriefSerializer,
    PositionSerializer,
    SkillSerializer,
)

__all__ = [
    # auth
    "EmailSerializer",
    "EmailVerifySerializer",
    "RegisterSerializer",
    # employee
    "EmployeeSerializer",
    "EmployeeListSerializer",
    "EmployeeBriefSerializer",
    "ProfilePatchSerializer",
    # department
    "DepartmentSerializer",
    "DepartmentBriefSerializer",
    "SetHeadInput",
    "AddMemberInput",
    "RemoveMemberInput",
    "SetMemberRoleInput",
    # shared
    "SkillSerializer",
    "PositionBriefSerializer",
    "PositionSerializer",
    "EmployeeActionSerializer",
    # role
    "DepartmentRoleSerializer",
    "GroupSerializer",
]
