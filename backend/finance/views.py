"""Views for finance app."""

from django.contrib.auth.decorators import login_required
from django.shortcuts import render


@login_required
def finance_dashboard(request):
    """
    Отображает финансовую панель с встроенным Яндекс.Диском.
    """
    context = {
        "yandex_disk_url": "https://disk.yandex.ru/i/0JWL-v5zyWJi0Q"
    }
    return render(request, "finance/dashboard.html", context)
