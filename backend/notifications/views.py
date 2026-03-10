"""
Views для приложения notifications.

Обслуживание Service Worker и других статических ресурсов.
"""
from django.http import FileResponse, HttpResponse
from pathlib import Path


def serve_service_worker(request):
    """
    Обслуживает Service Worker для Web Push уведомлений.
    
    Service Worker должен отдаваться с правильными заголовками:
    - content-type: application/javascript
    - Cache-Control: no-cache (всегда свежая версия)
    - Service-Worker-Allowed: / (контроль всего домена)
    """
    sw_path = Path(__file__).parent / 'static' / 'notifications' / 'sw.js'
    
    try:
        response = FileResponse(
            open(sw_path, 'rb'),
            content_type='application/javascript; charset=utf-8',
            status=200
        )
        # Отключаем кэширование для sw.js (всегда получаем свежую версию)
        response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response['Pragma'] = 'no-cache'
        response['Expires'] = '0'
        # Service-Worker-Allowed позволяет контролировать весь домен
        response['Service-Worker-Allowed'] = '/'
        return response
    except FileNotFoundError as e:
        return HttpResponse(
            f"Service Worker not found: {sw_path}",
            status=500
        )
    except Exception as e:
        return HttpResponse(
            f"Error serving Service Worker: {e}",
            status=500
        )
