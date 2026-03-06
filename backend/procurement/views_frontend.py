"""
HTML Views для модуля закупок (Frontend).

Все данные загружаются через API на клиенте.
Views только рендерят layout и передают минимальный контекст.
"""

from django.contrib.auth.decorators import login_required
from django.shortcuts import render


@login_required
def dashboard(request):
    """Главная страница модуля закупок.
    
    Данные загружаются через API:
    - /api/procurement/stats/overview/ — статистика
    - /api/procurement/budgets/my-department/ — бюджет отдела
    - /api/procurement/requests/?ordering=-created_at&page_size=5 — последние заявки
    """
    return render(request, 'procurement/dashboard.html', {})


@login_required
def request_list(request):
    """Список заявок на закупку.
    
    Данные загружаются через API:
    - /api/procurement/requests/ — с фильтрами
    - /api/v1/departments/ — для фильтра по отделам
    """
    scope = request.GET.get('scope', 'mine')
    user = request.user
    
    # Читаем фильтры из GET параметров
    filters = {
        'status': request.GET.get('status', ''),
        'urgency': request.GET.get('urgency', ''),
        'period': request.GET.get('period', ''),
    }
    
    # Определяем доступные представления
    can_view_department = user.departments.exists()
    can_view_all = (
        user.is_staff or user.is_superuser or
        user.has_perm('procurement.view_procurementrequest') or
        user.has_perm('procurement.change_procurementrequest')
    )
    
    return render(request, 'procurement/request_list.html', {
        'scope': scope,
        'show_tabs': True,
        'can_view_department': can_view_department,
        'can_view_all': can_view_all,
        'filters': filters,
    })
@login_required
def my_requests(request):
    """Мои заявки — редирект на request_list."""
    from django.shortcuts import redirect
    return redirect('procurement_frontend:request_list')


@login_required
def pending_approvals(request):
    """Заявки на согласовании.
    
    Данные загружаются через API:
    - /api/procurement/requests/pending_approvals/
    """
    user = request.user
    
    # Определяем доступные представления
    can_view_department = user.departments.exists()
    can_view_all = (
        user.is_staff or user.is_superuser or
        user.has_perm('procurement.view_procurementrequest') or
        user.has_perm('procurement.change_procurementrequest')
    )
    
    return render(request, 'procurement/request_list.html', {
        'scope': 'pending',
        'page_title': 'На согласовании',
        'show_tabs': True,
        'can_view_department': can_view_department,
        'can_view_all': can_view_all,
    })


@login_required
@login_required
def request_detail(request, pk):
    """Детальная страница заявки.
    
    Загружает данные из БД и передаёт в шаблон.
    
    Права на редактирование (can_edit):
    - Админы/Staff → любая заявка в DRAFT
    - Модельные права (change_procurementrequest) → любая заявка в DRAFT
    - Автор заявки → своя заявка в DRAFT
    - Начальник отдела → заявки своего отдела в DRAFT
    
    Права на согласование (can_approve):
    - Пользователи с активным approval для этой заявки
    """
    from django.shortcuts import get_object_or_404
    from procurement.models import ProcurementRequest
    
    request_obj = get_object_or_404(
        ProcurementRequest.objects.select_related(
            'department', 'requestor', 'executor'
        ).prefetch_related('items', 'approvals__approver'),
        pk=pk
    )
    
    user = request.user
    
    # Проверяем права на редактирование (синхронизировано с API)
    can_edit = False
    if request_obj.is_editable:  # Только DRAFT
        # Админы могут редактировать
        if user.is_superuser or user.is_staff:
            can_edit = True
        # Модельные права
        elif user.has_perm('procurement.change_procurementrequest'):
            can_edit = True
        # Автор заявки
        elif request_obj.requestor == user:
            can_edit = True
        # Начальник отдела
        elif request_obj.department.head == user:
            can_edit = True
    
    # Проверяем права на согласование
    can_approve = (
        request_obj.approvals.filter(
            approver=user,
            status='pending'
        ).exists()
    )
    
    return render(request, 'procurement/request_detail.html', {
        'request_id': pk,
        'request_obj': request_obj,
        'can_edit': can_edit,
        'can_approve': can_approve,
    })


@login_required
def request_create(request):
    """Страница создания заявки.
    
    Данные загружаются через API:
    - /api/v1/departments/ — список отделов
    Создание через:
    - POST /api/procurement/requests/
    """
    return render(request, 'procurement/request_form.html', {
        'page_title': 'Новая заявка',
        'request_id': None,
    })


@login_required
def request_edit(request, pk):
    """Страница редактирования заявки.
    
    Данные загружаются через API:
    - /api/v1/procurement/requests/{pk}/ — данные заявки
    - /api/v1/departments/ — список отделов
    Обновление через:
    - PATCH /api/v1/procurement/requests/{pk}/
    """
    return render(request, 'procurement/request_form.html', {
        'page_title': 'Редактирование заявки',
        'request_id': pk,
    })


@login_required
def equipment_list(request):
    """Список оборудования.
    
    Данные загружаются через API:
    - /api/procurement/equipment/ — список с фильтрами
    - /api/procurement/equipment-categories/ — категории для фильтра
    - /api/v1/departments/ — отделы для фильтра
    - /api/procurement/equipment/create-options/ — при создании
    """
    return render(request, 'procurement/equipment_list.html', {})


@login_required
def equipment_detail(request, pk):
    """Детальная страница оборудования.
    
    Загружает данные из БД и передаёт в шаблон.
    
    Права на управление (can_manage):
    - Админы/Staff → любое оборудование
    - Начальник отдела → оборудование своего отдела
    - Ответственный за оборудование → своё оборудование
    """
    from django.shortcuts import get_object_or_404
    from procurement.models import Equipment
    
    equipment = get_object_or_404(
        Equipment.objects.select_related(
            'department',
            'department__head',
            'category',
            'responsible_person',
            'procurement_item',
            'procurement_item__request'
        ).prefetch_related(
            'maintenance_history',
            'transfer_logs__from_department',
            'transfer_logs__to_department',
            'transfer_logs__from_person',
            'transfer_logs__to_person'
        ),
        pk=pk
    )
    
    user = request.user
    
    # Проверяем права на управление
    can_manage = False
    if user.is_superuser or user.is_staff:
        can_manage = True
    elif equipment.department and equipment.department.head == user:
        can_manage = True
    elif equipment.responsible_person == user:
        can_manage = True
    
    return render(request, 'procurement/equipment_detail.html', {
        'equipment': equipment,
        'can_manage': can_manage,
    })


# =============================================================================
# БЮДЖЕТЫ
# =============================================================================

@login_required
def budget_list(request):
    """Список бюджетов.
    
    Данные загружаются через API:
    - /api/procurement/budgets/ — список с фильтрами
    - /api/v1/departments/ — отделы для фильтра
    """
    return render(request, 'procurement/budget_list.html', {})


@login_required
def budget_create(request):
    """Создание бюджета.
    
    Данные загружаются через API:
    - /api/v1/departments/ — список отделов
    Создание через:
    - POST /api/procurement/budgets/
    """
    return render(request, 'procurement/budget_form.html', {
        'budget_id': None,
    })


@login_required
def budget_edit(request, pk):
    """Редактирование бюджета.
    
    Данные загружаются через API:
    - /api/procurement/budgets/{pk}/ — текущие данные
    - /api/v1/departments/ — список отделов
    Обновление через:
    - PATCH /api/procurement/budgets/{pk}/
    """
    return render(request, 'procurement/budget_form.html', {
        'budget_id': pk,
    })
