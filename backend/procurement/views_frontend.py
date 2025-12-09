"""
HTML Views для модуля закупок (Frontend).
"""

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, render, redirect
from django.utils import timezone

from employees.models import Department
from .forms import ProcurementRequestForm
from .models import (
    Budget,
    Equipment,
    EquipmentCategory,
    ProcurementRequest,
)
from .constants import ProcurementStatus

User = get_user_model()


@login_required
def dashboard(request):
    """Главная страница модуля закупок."""
    user = request.user
    now = timezone.now()
    quarter = (now.month - 1) // 3 + 1

    # Получаем отделы пользователя
    user_departments = user.departments.filter(
        employeedepartment__is_active=True
    )

    # Статистика
    stats = {
        'pending': ProcurementRequest.objects.filter(
            status=ProcurementStatus.PENDING
        ).count(),
        'approved': ProcurementRequest.objects.filter(
            status=ProcurementStatus.APPROVED
        ).count(),
        'equipment': Equipment.objects.count(),
    }

    # Бюджет отдела (берём первый отдел пользователя)
    budget = None
    if user_departments.exists():
        budget = Budget.objects.filter(
            department=user_departments.first(),
            year=now.year,
            quarter=quarter
        ).first()

    # Последние заявки (мои или моего отдела)
    recent_requests = ProcurementRequest.objects.filter(
        department__in=user_departments
    ).select_related(
        'department', 'requestor'
    ).order_by('-created_at')[:5]

    # Права на согласование
    can_approve = user.is_staff or user.headed_departments.exists()

    context = {
        'stats': stats,
        'budget': budget,
        'recent_requests': recent_requests,
        'can_approve': can_approve,
        'departments': Department.objects.all().order_by('name'),
    }
    return render(request, 'procurement/dashboard.html', context)


@login_required
def request_list(request):
    """Список заявок на закупку."""
    user = request.user
    scope = request.GET.get('scope', 'mine')

    # Базовый queryset
    queryset = ProcurementRequest.objects.select_related(
        'department', 'requestor'
    ).prefetch_related('items')

    # Фильтрация по области видимости
    if scope == 'mine':
        queryset = queryset.filter(requestor=user)
        page_title = 'Мои заявки'
    elif scope == 'department':
        user_departments = user.departments.filter(
            employeedepartment__is_active=True
        )
        queryset = queryset.filter(department__in=user_departments)
        page_title = 'Заявки отдела'
    elif scope == 'all' and user.is_staff:
        page_title = 'Все заявки'
    else:
        queryset = queryset.filter(requestor=user)
        page_title = 'Мои заявки'
        scope = 'mine'

    # Фильтры
    filters = {}
    if status := request.GET.get('status'):
        queryset = queryset.filter(status=status)
        filters['status'] = status
    if urgency := request.GET.get('urgency'):
        queryset = queryset.filter(urgency=urgency)
        filters['urgency'] = urgency

    # Сортировка
    queryset = queryset.order_by('-created_at')

    # Пагинация
    paginator = Paginator(queryset, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'requests': page_obj,
        'page_obj': page_obj,
        'page_title': page_title,
        'scope': scope,
        'filters': filters,
        'can_view_all': user.is_staff or user.headed_departments.exists(),
        'departments': Department.objects.all().order_by('name'),
    }
    return render(request, 'procurement/request_list.html', context)


@login_required
def my_requests(request):
    """Мои заявки."""
    return redirect('procurement:request_list', permanent=False)


@login_required
def pending_approvals(request):
    """Заявки на согласовании (для руководителей)."""
    user = request.user

    # Получаем отделы, которыми руководит пользователь
    headed_depts = user.headed_departments.all()

    if not headed_depts.exists() and not user.is_staff:
        return redirect('procurement:dashboard')

    queryset = ProcurementRequest.objects.filter(
        status=ProcurementStatus.PENDING
    ).select_related(
        'department', 'requestor'
    )

    # Для не-staff показываем только заявки своих отделов
    if not user.is_staff:
        queryset = queryset.filter(department__in=headed_depts)

    queryset = queryset.order_by('-created_at')

    paginator = Paginator(queryset, 20)
    page_obj = paginator.get_page(request.GET.get('page'))

    context = {
        'requests': page_obj,
        'page_obj': page_obj,
        'page_title': 'На согласовании',
        'scope': 'pending',
        'can_view_all': user.is_staff,
    }
    return render(request, 'procurement/request_list.html', context)


@login_required
def request_detail(request, pk):
    """Детальная страница заявки."""
    procurement_request = get_object_or_404(
        ProcurementRequest.objects.select_related(
            'department', 'requestor'
        ).prefetch_related(
            'items__supplier',
            'approvals__approver'
        ),
        pk=pk
    )

    context = {
        'request_obj': procurement_request,
        'can_edit': (
            procurement_request.requestor == request.user and
            procurement_request.status == ProcurementStatus.DRAFT
        ),
        'can_approve': (
            request.user.is_staff or
            request.user.headed_departments.filter(
                pk=procurement_request.department_id
            ).exists()
        ),
    }
    return render(request, 'procurement/request_detail.html', context)


@login_required
def request_create(request):
    """Страница/обработка создания заявки."""
    if request.method == 'POST':
        form = ProcurementRequestForm(request.POST, user=request.user)
        if form.is_valid():
            # Создаём заявку
            procurement_request = form.save(commit=False)
            procurement_request.requestor = request.user
            procurement_request.status = ProcurementStatus.DRAFT
            procurement_request.save()

            messages.success(
                request,
                f'Заявка "{procurement_request.title}" создана. '
                'Добавьте позиции и отправьте на согласование.'
            )
            return redirect(
                'procurement:request_detail',
                pk=procurement_request.pk
            )
        else:
            messages.error(request, 'Пожалуйста, исправьте ошибки в форме.')
    else:
        form = ProcurementRequestForm(user=request.user)

    context = {
        'form': form,
        'page_title': 'Новая заявка',
    }
    return render(request, 'procurement/request_form.html', context)


@login_required
def equipment_list(request):
    """Список оборудования с группировкой одинаковых позиций."""
    from collections import defaultdict
    
    queryset = Equipment.objects.select_related(
        'category', 'department', 'responsible_person'
    )

    # Фильтры
    filters = {}
    if category := request.GET.get('category'):
        queryset = queryset.filter(category_id=category)
        filters['category'] = category
    if status := request.GET.get('status'):
        queryset = queryset.filter(status=status)
        filters['status'] = status
    if department := request.GET.get('department'):
        queryset = queryset.filter(department_id=department)
        filters['department'] = department

    # Поиск
    if search := request.GET.get('q'):
        queryset = queryset.filter(
            name__icontains=search
        ) | queryset.filter(
            inventory_number__icontains=search
        )

    queryset = queryset.order_by('name', '-purchase_date')
    
    # Группировка по (название, категория, отдел, статус)
    grouped_equipment = defaultdict(list)
    for item in queryset:
        key = (
            item.name,
            item.category_id,
            item.department_id,
            item.status
        )
        grouped_equipment[key].append(item)
    
    # Преобразуем в список групп
    equipment_groups = []
    for key, items in grouped_equipment.items():
        # Первый элемент — представитель группы
        main_item = items[0]
        equipment_groups.append({
            'main': main_item,
            'items': items,
            'count': len(items),
            'is_group': len(items) > 1,
        })
    
    # Сортировка по имени
    equipment_groups.sort(key=lambda x: x['main'].name.lower())

    # Пагинация по группам
    paginator = Paginator(equipment_groups, 24)
    page_obj = paginator.get_page(request.GET.get('page'))

    # Получаем первый активный отдел пользователя
    user_department = request.user.departments.filter(
        employeedepartment__is_active=True
    ).first()
    
    # Получаем руководителя отдела (если есть)
    department_head = None
    if user_department:
        department_head = user_department.head

    context = {
        'equipment_groups': page_obj,
        'page_obj': page_obj,
        'filters': filters,
        'categories': EquipmentCategory.objects.all(),
        'departments': Department.objects.all(),
        'users': User.objects.filter(
            is_active=True
        ).order_by('last_name', 'first_name'),
        'can_manage': request.user.is_staff,
        'user_department': user_department,
        'department_head': department_head,
    }
    return render(request, 'procurement/equipment_list.html', context)


@login_required
def equipment_detail(request, pk):
    """Детальная страница оборудования."""
    equipment = get_object_or_404(
        Equipment.objects.select_related(
            'category', 'department', 'responsible_person'
        ).prefetch_related(
            'maintenance_history', 'transfer_logs'
        ),
        pk=pk
    )

    context = {
        'equipment': equipment,
        'can_manage': (
            request.user.is_staff or
            equipment.responsible_person == request.user
        ),
    }
    return render(request, 'procurement/equipment_detail.html', context)
