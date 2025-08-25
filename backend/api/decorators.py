from functools import wraps

from django.shortcuts import redirect
from django.urls import reverse

from .client import SESSION_KEY_ACCESS, load_config


def require_api_auth(view_func):
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not request.session.get(SESSION_KEY_ACCESS):
            login_url_name = load_config().login_url_name
            return redirect(reverse(login_url_name))
        return view_func(request, *args, **kwargs)

    return _wrapped
