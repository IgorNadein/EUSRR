"""
Ограничение доступа к определенным функциям по IP-адресу.
"""
import ipaddress
from functools import wraps
from typing import List

from django.conf import settings
from django.http import HttpResponse


def get_client_ip(request) -> str:
    """
    Получает реальный IP-адрес клиента из request.
    Учитывает заголовки прокси (X-Forwarded-For, X-Real-IP).
    """
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        # Берем первый IP из списка (клиентский IP)
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR', '')
    return ip


def is_local_ip(ip_address: str) -> bool:
    """
    Проверяет, является ли IP-адрес локальным.

    Локальными считаются:
    - 127.0.0.0/8 (localhost)
    - 10.0.0.0/8 (частная сеть класса A)
    - 172.16.0.0/12 (частная сеть класса B)
    - 192.168.0.0/16 (частная сеть класса C)
    - ::1 (IPv6 localhost)
    - fe80::/10 (IPv6 link-local)
    """
    try:
        ip = ipaddress.ip_address(ip_address)
        return ip.is_private or ip.is_loopback or ip.is_link_local
    except ValueError:
        # Невалидный IP - считаем небезопасным
        return False


def is_ip_allowed(ip_address: str, allowed_networks: List[str] = None) -> bool:
    """
    Проверяет, разрешен ли доступ с данного IP-адреса.

    Args:
        ip_address: IP-адрес для проверки
        allowed_networks: Список разрешенных сетей в формате CIDR
                         или отдельных IP. Если None, используется
                         REGISTRATION_ALLOWED_IPS из settings.

    Returns:
        True если IP разрешен, False иначе
    """
    if allowed_networks is None:
        # Проверяем настройки Django
        allowed_networks = getattr(settings, 'REGISTRATION_ALLOWED_IPS', None)

        # Если настройка не задана, разрешаем только локальные IP
        if allowed_networks is None:
            return is_local_ip(ip_address)

    # Пустой список = запретить всем
    if not allowed_networks:
        return False

    # Специальное значение для разрешения всех IP
    if allowed_networks == ['*'] or '*' in allowed_networks:
        return True

    try:
        ip = ipaddress.ip_address(ip_address)

        for network_str in allowed_networks:
            # Проверяем, является ли это сетью (содержит /) или отдельным IP
            if '/' in network_str:
                network = ipaddress.ip_network(network_str, strict=False)
                if ip in network:
                    return True
            else:
                # Отдельный IP-адрес
                allowed_ip = ipaddress.ip_address(network_str)
                if ip == allowed_ip:
                    return True

        return False
    except ValueError:
        # Невалидный IP - запрещаем
        return False


def local_ip_required(view_func):
    """
    Декоратор для ограничения доступа к view только с локальных IP.

    Использование:
        @local_ip_required
        def my_view(request):
            ...
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        client_ip = get_client_ip(request)

        if not is_ip_allowed(client_ip):
            return HttpResponse(
                '<h1>403 Forbidden</h1>'
                '<p>Регистрация доступна только из локальной сети.</p>'
                f'<p>Ваш IP: {client_ip}</p>',
                status=403,
                content_type='text/html; charset=utf-8'
            )

        return view_func(request, *args, **kwargs)

    return wrapper


def local_ip_required_api(view_class):
    """
    Декоратор для ограничения доступа к API View только с локальных IP.

    Использование:
        @local_ip_required_api
        class MyAPIView(APIView):
            ...
    """
    original_dispatch = view_class.dispatch

    def dispatch_wrapper(self, request, *args, **kwargs):
        from rest_framework.response import Response
        from rest_framework import status as drf_status

        client_ip = get_client_ip(request)

        if not is_ip_allowed(client_ip):
            return Response(
                {
                    'detail': 'Регистрация доступна только из локальной сети.',
                    'client_ip': client_ip
                },
                status=drf_status.HTTP_403_FORBIDDEN
            )

        return original_dispatch(self, request, *args, **kwargs)

    view_class.dispatch = dispatch_wrapper
    return view_class
