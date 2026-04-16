from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from employees.models import Department, EmployeeDepartment, RoleAssignment

from .services import delete_department_calendar, sync_department_calendar_if_bound


@receiver(post_delete, sender=Department)
def delete_department_calendar_on_department_delete(sender, instance, **kwargs):
    delete_department_calendar(instance.id)


@receiver(post_save, sender=EmployeeDepartment)
def sync_department_calendar_on_member_save(sender, instance, **kwargs):
    sync_department_calendar_if_bound(instance.department)


@receiver(post_delete, sender=EmployeeDepartment)
def sync_department_calendar_on_member_delete(sender, instance, **kwargs):
    sync_department_calendar_if_bound(instance.department)


@receiver(post_save, sender=RoleAssignment)
def sync_department_calendar_on_role_assignment_save(
    sender, instance, **kwargs
):
    sync_department_calendar_if_bound(instance.role.department)


@receiver(post_delete, sender=RoleAssignment)
def sync_department_calendar_on_role_assignment_delete(
    sender, instance, **kwargs
):
    sync_department_calendar_if_bound(instance.role.department)
