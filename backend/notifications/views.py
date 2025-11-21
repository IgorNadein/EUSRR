from django.shortcuts import render
from django.contrib.auth.decorators import login_required


@login_required
def notification_list(request):
    """Страница списка уведомлений с фильтрами и пагинацией"""
    return render(request, 'notifications/notification_list.html')


@login_required
def notification_settings(request):
    """Страница настроек уведомлений"""
    from django.conf import settings
    
    context = {
        'telegram_bot_username': getattr(
            settings, 
            'TELEGRAM_BOT_USERNAME', 
            'eusrr_bot'
        )
    }
    return render(request, 'notifications/notification_settings.html', context)

