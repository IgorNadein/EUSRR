# backend\employees\views_front.py
from feed.models import Post
import os
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.urls import reverse
from django.conf import settings

from .forms import ProfileUpdateForm
from .models import Employee, Department
from bots.models import BotSubscriber

from dotenv import load_dotenv
load_dotenv()

USERNAME_TELEGRAM_BOT = os.getenv('USERNAME_TELEGRAM_BOT')


@login_required
def profile(request):
    """Страница своего профиля с лентой публикаций и личной инфой"""
    employee = request.user
    posts = Post.objects.filter(author=employee).order_by('-created_at')[:10]
    form = ProfileUpdateForm(instance=employee)
    return render(request, 'employees/profile.html', {
        'form': form,
        'employee': employee,
        'own': True,
        'posts': posts,
    })


@login_required
def employee_detail(request, pk):
    """Страница чужого профиля с инфо и лентой публикаций"""
    employee = get_object_or_404(Employee, pk=pk)
    if employee == request.user:
        return redirect('employees:profile')
    posts = Post.objects.filter(author=employee).order_by('-created_at')[:10]
    return render(request, 'employees/profile.html', {
        'employee': employee,
        'own': False,
        'posts': posts,
    })


@login_required
def avatar_remove(request):
    """Удаление аватарки пользователя"""
    if request.method == 'POST':
        user = request.user
        if user.avatar:
            user.avatar.delete(save=True)
            messages.success(request, 'Аватар успешно удалён.')
        return redirect('employees:profile')
    return redirect('employees:profile')


@login_required
def employees_list(request):
    """Список всех сотрудников (виден только авторизованным)"""
    employees = Employee.objects.select_related().order_by('last_name', 'first_name')
    return render(request, 'employees/employees_list.html', {
        'employees': employees,
    })


@login_required
def department_list(request):
    """Список отделов"""
    departments = Department.objects.all().order_by('name')
    return render(request, 'employees/department_list.html', {
        'departments': departments,
    })


@login_required
def department_detail(request, pk):
    """Детальная страница отдела"""
    department = get_object_or_404(Department, pk=pk)
    employees = department.employees.all().select_related('employee')
    return render(request, 'employees/department_detail.html', {
        'department': department,
        'employees': employees,
    })
