# employees/api_client.py
from django.urls import reverse
from django.http import HttpRequest
import requests


class APIError(Exception):
    pass


def _json_safe(x):
    try:
        from phonenumber_field.phonenumber import PhoneNumber
    except Exception:
        PhoneNumber = None
    if isinstance(x, dict):
        return {k: _json_safe(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_json_safe(v) for v in x]
    if PhoneNumber and isinstance(x, PhoneNumber):
        return x.as_e164 or x.raw_input or str(x)
    return x


def _abs_url(request: HttpRequest, url_name: str, **kwargs) -> str:
    rel = reverse(url_name, kwargs=kwargs or None)
    return request.build_absolute_uri(rel)


def api_post(request: HttpRequest, url_name: str, payload: dict, **kwargs):
    url = _abs_url(request, url_name)
    payload = _json_safe(payload or {})
    headers = {"Accept": "application/json"}
    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=10, **kwargs)
    except requests.RequestException as e:
        raise APIError(f"api_network_error: {e}")
    try:
        data = resp.json()
    except ValueError:
        # ← Вот тут будем видеть «почему»
        snippet = (resp.text or "")[:500]
        raise APIError(f"api_bad_json status={resp.status_code} body={snippet!r}")
    return resp.status_code, data


def api_get(request: HttpRequest, url_name: str, params: dict | None = None, **kwargs):
    url = _abs_url(request, url_name)
    headers = {"Accept": "application/json"}
    try:
        resp = requests.get(
            url, params=params or {}, headers=headers, timeout=10, **kwargs
        )
    except requests.RequestException as e:
        raise APIError(f"api_network_error: {e}")
    try:
        data = resp.json()
    except ValueError:
        snippet = (resp.text or "")[:500]
        raise APIError(f"api_bad_json status={resp.status_code} body={snippet!r}")
    return resp.status_code, data
