# backend\api\client.py
from dataclasses import dataclass
from typing import Any, Dict, Optional

import requests
from django.conf import settings


# ==== Настройки с дефолтами ====
@dataclass
class ApiConfig:
    base_url: str
    token_obtain_path: str = "/auth/token/"
    token_refresh_path: str = "/auth/token/refresh/"
    timeout: int = 15
    default_headers: Dict[str, str] = None
    login_url_name: str = "auth_front:login"  # куда редиректить, если токены протухли


def load_config() -> ApiConfig:
    base = getattr(settings, "API_BASE_URL", "http://localhost:8000/api")
    return ApiConfig(
        base_url=base.rstrip("/"),
        token_obtain_path=getattr(settings, "API_TOKEN_OBTAIN_PATH", "/auth/token/"),
        token_refresh_path=getattr(
            settings, "API_TOKEN_REFRESH_PATH", "/auth/token/refresh/"
        ),
        timeout=getattr(settings, "API_TIMEOUT", 15),
        default_headers=getattr(
            settings, "API_DEFAULT_HEADERS", {"Accept": "application/json"}
        ),
        login_url_name=getattr(settings, "API_LOGIN_URL_NAME", "auth_front:login"),
    )


# ==== Ответ-обёртка ====
@dataclass
class ApiResponse:
    ok: bool
    status: int
    json: Any | None
    text: str | None


SESSION_KEY_ACCESS = "api.jwt_access"
SESSION_KEY_REFRESH = "api.jwt_refresh"


class ApiClient:
    """
    Унифицированный клиент DRF-API с JWT:
    - хранит токены в request.session;
    - автоматический refresh при 401 (1 попытка);
    - единая сессия requests.Session;
    - get/post/patch/put/delete с одинаковыми сигнатурами.
    """

    def __init__(self, request, config: Optional[ApiConfig] = None):
        self.request = request
        self.cfg = config or load_config()
        self.session = requests.Session()
        self.access = request.session.get(SESSION_KEY_ACCESS)
        self.refresh = request.session.get(SESSION_KEY_REFRESH)

    # --- базовое ---
    def _auth_headers(self) -> Dict[str, str]:
        return {"Authorization": f"Bearer {self.access}"} if self.access else {}

    def _make_url(self, path: str) -> str:
        return f"{self.cfg.base_url}/{path.lstrip('/')}"
    
    def _request(
        self,
        method: str,
        path: str,
        *,
        params=None,
        json=None,
        data=None,
        files=None,
        headers=None,
        retry=True,
    ) -> ApiResponse:
        url = self._make_url(path)
        hdrs = dict(self.cfg.default_headers or {})
        # Не выставляем Content-Type вручную — requests сделает это сам (особенно важно для multipart)
        if headers:
            # если вдруг передали Content-Type, но у нас files — лучше его удалить
            if files and "Content-Type" in headers:
                headers = {k: v for k, v in headers.items() if k.lower() != "content-type"}
            hdrs.update(headers)
        hdrs.update(self._auth_headers())

        resp = self.session.request(
            method,
            url,
            params=params,
            json=None if files or data else json,  # при multipart json не используем
            data=data,
            files=files,
            headers=hdrs,
            timeout=self.cfg.timeout,
        )

        if resp.status_code == 401 and retry and self.refresh:
            if self.refresh_tokens():
                hdrs = dict(self.cfg.default_headers or {})
                hdrs.update(self._auth_headers())
                resp = self.session.request(
                    method,
                    url,
                    params=params,
                    json=None if files or data else json,
                    data=data,
                    files=files,
                    headers=hdrs,
                    timeout=self.cfg.timeout,
                )

        try:
            data_json = resp.json()
        except Exception:
            data_json = None
        return ApiResponse(ok=resp.ok, status=resp.status_code, json=data_json, text=resp.text)
    
    # --- публичные методы HTTP ---
    def get(self, path: str, **kw) -> ApiResponse:
        return self._request("GET", path, **kw)

    def post(self, path: str, **kw) -> ApiResponse:
        return self._request("POST", path, **kw)

    def patch(self, path: str, **kw) -> ApiResponse:
        return self._request("PATCH", path, **kw)

    def put(self, path: str, **kw) -> ApiResponse:
        return self._request("PUT", path, **kw)

    def delete(self, path: str, **kw) -> ApiResponse:
        return self._request("DELETE", path, **kw)

    # --- аутентификация ---
    def login(self, email: str, password: str) -> bool:
        url = self._make_url(self.cfg.token_obtain_path)
        resp = self.session.post(url, json={"email": email, "password": password}, timeout=self.cfg.timeout)
        if resp.status_code >= 400:
            return False
        if "application/json" not in (resp.headers.get("Content-Type") or ""):
            return False
        try:
            data = resp.json()
        except ValueError:
            return False
        access, refresh = data.get("access"), data.get("refresh")
        if not access or not refresh:
            return False
        self.access = access
        self.refresh = refresh
        self.request.session["api.jwt_access"] = access
        self.request.session["api.jwt_refresh"] = refresh
        self.request.session.modified = True
        return True

    def logout(self):
        self.request.session.pop(SESSION_KEY_ACCESS, None)
        self.request.session.pop(SESSION_KEY_REFRESH, None)
        self.request.session.modified = True
        self.access = None
        self.refresh = None

    def refresh_tokens(self) -> bool:
        url = self._make_url(self.cfg.token_refresh_path)
        resp = self.session.post(
            url, json={"refresh": self.refresh}, timeout=self.cfg.timeout
        )
        if resp.ok:
            data = resp.json()
            new_access = data.get("access")
            if new_access:
                self.access = new_access
                self.request.session[SESSION_KEY_ACCESS] = new_access
                self.request.session.modified = True
                return True
        # не смогли рефрешнуть — чистим
        self.logout()
        return False


# Удобный фабричный хелпер
def get_api_client(request) -> ApiClient:
    return ApiClient(request)
