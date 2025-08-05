from django.contrib.auth.decorators import login_required
from .models import Request
from .forms import RequestStatusForm, RequestForm

from django.contrib.auth.decorators import user_passes_test
from django.shortcuts import render
from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages


@login_required
def request_create(request):
    """Создать новое заявление"""
    if request.method == 'POST':
        form = RequestForm(request.POST)
        if form.is_valid():
            req = form.save(commit=False)
            req.employee = request.user
            req.save()
            messages.success(request, "Заявление отправлено!")
            return redirect('requests_app:my_requests')
    else:
        form = RequestForm()
    return render(request, 'requests_app/request_form.html', {'form': form})


@login_required
def request_detail(request, pk):
    req = get_object_or_404(Request, pk=pk, employee=request.user)
    return render(request, 'requests_app/request_detail.html', {'request_obj': req})


def is_hr_or_head(user):
    return user.is_staff or user.groups.filter(name__in=['HR', 'Heads']).exists()


@user_passes_test(is_hr_or_head)
def all_requests(request):
    """Список всех заявлений (для HR/руководителя)"""
    # Для HR — все заявки, для руководителя — только по его отделу
    if request.user.is_staff or request.user.groups.filter(name='HR').exists():
        requests_qs = Request.objects.all().order_by('-created_at')
    else:
        # Показываем заявки сотрудников его отдела
        requests_qs = Request.objects.filter(
            employee__positions__department__head=request.user).distinct().order_by('-created_at')
    return render(request, 'requests_app/all_requests.html', {'requests': requests_qs})


@user_passes_test(is_hr_or_head)
def request_process(request, pk):
    req = get_object_or_404(Request, pk=pk)
    if request.method == 'POST':
        form = RequestStatusForm(request.POST, instance=req)
        if form.is_valid():
            form.save()
            messages.success(request, "Статус заявления обновлён.")
            return redirect('requests_app:all_requests')
    else:
        form = RequestStatusForm(instance=req)
    return render(request, 'requests_app/request_process.html', {
        'request_obj': req,
        'form': form
    })


@login_required
def my_requests(request):
    """Список всех заявлений текущего пользователя"""
    requests_qs = Request.objects.filter(
        employee=request.user).order_by('-created_at')
    return render(request, 'requests_app/my_requests.html', {
        'requests': requests_qs,
    })


@login_required
def request_delete(request, pk):
    """Удаление (отзыв) собственного заявления, если оно ещё не рассмотрено"""
    req = get_object_or_404(Request, pk=pk, employee=request.user)
    if req.status != 'pending':
        messages.error(
            request, "Нельзя отозвать заявление, уже рассмотренное HR или руководителем.")
        return redirect('requests_app:my_requests')
    if request.method == "POST":
        req.delete()
        messages.success(request, "Заявление успешно отозвано и удалено.")
        return redirect('requests_app:my_requests')
    return render(request, 'requests_app/request_confirm_delete.html', {'request_obj': req})
