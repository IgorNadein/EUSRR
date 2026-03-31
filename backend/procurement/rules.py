"""
django-rules: декларативные правила доступа для procurement (закупки)

Правила используются для проверки permissions на уровне объектов.
https://github.com/dfunckt/django-rules
"""

import rules


# -----------------------------------------------------------------------------
# ПРЕДИКАТЫ (predicates)
# -----------------------------------------------------------------------------

@rules.predicate
def is_superuser(user):
    """Суперпользователь имеет все права"""
    return user.is_superuser


@rules.predicate
def is_procurement_manager(user):
    """
    Пользователь является менеджером по закупкам.
    Адаптируйте под вашу логику (по должности, группе и т.д.)
    """
    if not hasattr(user, 'position'):
        return False

    position_name = getattr(user.position, 'name', '').lower()
    return any(keyword in position_name for keyword in [
        'закупк', 'снабжен', 'procurement', 'supply'
    ])


@rules.predicate
def is_purchase_request_author(user, purchase_request):
    """Пользователь является автором заявки на закупку"""
    if purchase_request is None:
        return False

    return (
        purchase_request.created_by == user or
        getattr(purchase_request, 'author', None) == user
    )


@rules.predicate
def is_purchase_request_approver(user, purchase_request):
    """Пользователь назначен согласующим для заявки на закупку"""
    if purchase_request is None:
        return False

    # Проверка через approvers
    if hasattr(purchase_request, 'approvers'):
        return user in purchase_request.approvers.all()

    # Проверка через approval_chain
    if hasattr(purchase_request, 'approval_chain'):
        return purchase_request.approval_chain.filter(approver=user).exists()

    return False


@rules.predicate
def is_department_purchase_request(user, purchase_request):
    """Заявка на закупку относится к отделу пользователя"""
    if purchase_request is None or not hasattr(user, 'department'):
        return False

    if hasattr(purchase_request, 'department'):
        return purchase_request.department == user.department

    # Проверка через автора
    if hasattr(
            purchase_request,
            'created_by') and hasattr(
            purchase_request.created_by,
            'department'):
        return purchase_request.created_by.department == user.department

    return False


@rules.predicate
def can_approve_purchases(user):
    """
    Пользователь может согласовывать закупки.
    Адаптируйте под вашу логику (по должности, бюджетным лимитам и т.д.)
    """
    if not hasattr(user, 'position'):
        return False

    position_name = getattr(user.position, 'name', '').lower()
    return any(keyword in position_name for keyword in [
        'руководитель', 'начальник', 'директор', 'финансов'
    ])


@rules.predicate
def is_supplier_contact(user, supplier):
    """Пользователь является контактным лицом поставщика"""
    if supplier is None:
        return False

    if hasattr(supplier, 'contact_person'):
        return supplier.contact_person == user

    if hasattr(supplier, 'managers'):
        return user in supplier.managers.all()

    return False


@rules.predicate
def is_contract_manager(user, contract):
    """Пользователь является менеджером договора"""
    if contract is None:
        return False

    if hasattr(contract, 'manager'):
        return contract.manager == user

    if hasattr(contract, 'responsible_person'):
        return contract.responsible_person == user

    return False


@rules.predicate
def can_manage_suppliers(user):
    """Пользователь может управлять поставщиками"""
    return is_procurement_manager(user) or is_superuser(user)


# -----------------------------------------------------------------------------
# ПРАВИЛА (rules)
# -----------------------------------------------------------------------------

# Просмотр заявки на закупку
rules.add_rule(
    'procurement.view_purchase_request',
    is_superuser | is_purchase_request_author | is_procurement_manager |
    is_purchase_request_approver | can_approve_purchases
)

# Создание заявки на закупку
rules.add_rule(
    'procurement.create_purchase_request',
    rules.is_authenticated  # Любой сотрудник может создать заявку
)

# Изменение заявки на закупку
rules.add_rule(
    'procurement.change_purchase_request',
    is_superuser | is_purchase_request_author | is_procurement_manager
)

# Удаление заявки на закупку
rules.add_rule(
    'procurement.delete_purchase_request',
    is_superuser | is_purchase_request_author
)

# Согласование заявки на закупку
rules.add_rule('procurement.approve_purchase_request', is_superuser |
               is_purchase_request_approver | can_approve_purchases | is_procurement_manager)

# Изменение статуса заявки
rules.add_rule(
    'procurement.change_request_status',
    is_superuser | is_procurement_manager | can_approve_purchases
)

# Просмотр поставщика
rules.add_rule(
    'procurement.view_supplier',
    is_superuser | is_procurement_manager | is_supplier_contact
)

# Создание/изменение поставщика
rules.add_rule(
    'procurement.manage_supplier',
    is_superuser | can_manage_suppliers
)

# Удаление поставщика
rules.add_rule(
    'procurement.delete_supplier',
    is_superuser
)

# Просмотр договора
rules.add_rule(
    'procurement.view_contract',
    is_superuser | is_contract_manager | is_procurement_manager
)

# Создание/изменение договора
rules.add_rule(
    'procurement.manage_contract',
    is_superuser | is_contract_manager | can_manage_suppliers
)

# Удаление договора
rules.add_rule(
    'procurement.delete_contract',
    is_superuser
)

# Просмотр всех заявок (для менеджеров)
rules.add_rule(
    'procurement.view_all_requests',
    is_superuser | is_procurement_manager | can_approve_purchases
)

# Просмотр отчётов по закупкам
rules.add_rule(
    'procurement.view_reports',
    is_superuser | is_procurement_manager | can_approve_purchases
)

# Экспорт данных по закупкам
rules.add_rule(
    'procurement.export_data',
    is_superuser | is_procurement_manager
)


# -----------------------------------------------------------------------------
# ИСПОЛЬЗОВАНИЕ В КОДЕ
# -----------------------------------------------------------------------------

"""
# В views:
from django.core.exceptions import PermissionDenied
import rules

def purchase_request_detail(request, pk):
    purchase_request = get_object_or_404(PurchaseRequest, pk=pk)

    if not rules.test_rule('procurement.view_purchase_request', request.user, purchase_request):
        raise PermissionDenied("У вас нет доступа к этой заявке")

    return render(request, 'procurement/request_detail.html', {
        'request': purchase_request
    })


def approve_purchase_request(request, pk):
    purchase_request = get_object_or_404(PurchaseRequest, pk=pk)

    if not rules.test_rule('procurement.approve_purchase_request', request.user, purchase_request):
        return JsonResponse({'error': 'Нет прав на согласование'}, status=403)

    purchase_request.status = 'approved'
    purchase_request.approved_by = request.user
    purchase_request.approved_at = timezone.now()
    purchase_request.save()

    return JsonResponse({'success': True})


def supplier_list(request):
    # Фильтрация: только доступные поставщики
    if rules.test_rule('procurement.view_all_requests', request.user, None):
        suppliers = Supplier.objects.all()
    else:
        suppliers = Supplier.objects.filter(
            Q(contact_person=request.user) | Q(managers=request.user)
        )

    return render(request, 'procurement/suppliers.html', {'suppliers': suppliers})


# В templates:
{% load rules %}

{% has_rule 'procurement.approve_purchase_request' user purchase_request as can_approve %}
{% if can_approve and purchase_request.status == 'pending' %}
    <form method="post" action="{% url 'procurement:approve' purchase_request.pk %}">
        {% csrf_token %}
        <button type="submit" class="btn btn-success">Согласовать</button>
    </form>
    <form method="post" action="{% url 'procurement:reject' purchase_request.pk %}">
        {% csrf_token %}
        <button type="submit" class="btn btn-danger">Отклонить</button>
    </form>
{% endif %}

{% has_rule 'procurement.manage_supplier' user None as can_manage %}
{% if can_manage %}
    <a href="{% url 'procurement:supplier_create' %}" class="btn btn-primary">
        Добавить поставщика
    </a>
{% endif %}


# В DRF permissions:
from rest_framework import permissions
import rules

class PurchaseRequestPermission(permissions.BasePermission):
    def has_permission(self, request, view):
        if request.method == 'POST':
            return rules.test_rule('procurement.create_purchase_request', request.user, None)
        return True

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return rules.test_rule('procurement.view_purchase_request', request.user, obj)
        elif request.method in ['PUT', 'PATCH']:
            return rules.test_rule('procurement.change_purchase_request', request.user, obj)
        elif request.method == 'DELETE':
            return rules.test_rule('procurement.delete_purchase_request', request.user, obj)
        return False


class SupplierPermission(permissions.BasePermission):
    def has_permission(self, request, view):
        if request.method == 'POST':
            return rules.test_rule('procurement.manage_supplier', request.user, None)
        return True

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return rules.test_rule('procurement.view_supplier', request.user, obj)
        elif request.method in ['PUT', 'PATCH']:
            return rules.test_rule('procurement.manage_supplier', request.user, None)
        elif request.method == 'DELETE':
            return rules.test_rule('procurement.delete_supplier', request.user, None)
        return False


# Фильтрация QuerySet:
from django.db.models import Q

def get_accessible_purchase_requests(user):
    if rules.test_rule('procurement.view_all_requests', user, None):
        return PurchaseRequest.objects.all()

    return PurchaseRequest.objects.filter(
        Q(created_by=user) |  # Созданные пользователем
        Q(approvers=user) |  # Требующие согласования
        Q(department=user.department)  # Заявки отдела
    ).distinct()


def get_accessible_suppliers(user):
    if rules.test_rule('procurement.view_all_requests', user, None):
        return Supplier.objects.all()

    return Supplier.objects.filter(
        Q(contact_person=user) | Q(managers=user)
    ).distinct()
"""
