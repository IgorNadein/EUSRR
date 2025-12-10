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
    
    return render(request, 'procurement/request_list.html', {
        'scope': scope,
        'show_tabs': True,
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
    return render(request, 'procurement/request_list.html', {
        'scope': 'pending',
        'page_title': 'На согласовании',
        'show_tabs': True,
    })


@login_required
def request_detail(request, pk):
    """Детальная страница заявки.
    
    Данные загружаются через API:
    - /api/procurement/requests/{pk}/
    - /api/procurement/equipment/create-options/ — при создании оборудования
    - /api/procurement/equipment-categories/ — категории
    """
    return render(request, 'procurement/request_detail.html', {
        'request_id': pk,
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
    
    Данные загружаются через API:
    - /api/procurement/equipment/{pk}/
    """
    return render(request, 'procurement/equipment_detail.html', {
        'equipment_id': pk,
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
