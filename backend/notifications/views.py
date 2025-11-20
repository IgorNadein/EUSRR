from django.shortcuts import render
from django.contrib.auth.decorators import login_required


@login_required
def notification_list(request):
    """Страница списка уведомлений с фильтрами и пагинацией"""
    return render(request, 'notifications/notification_list_new.html')


@login_required
def notification_settings(request):
    """Страница настроек уведомлений"""
    return render(request, 'notifications/notification_settings_new.html')

