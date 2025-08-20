from django.shortcuts import redirect
from django.urls import reverse

class AuthRequiredMiddleware:
    """
    Разрешает доступ неавторизованным пользователям только к страницам входа и регистрации.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        allowed_paths = [
            reverse('login'),
            reverse('employees:register'),
            reverse('employees:email_verify'),
            reverse('employees:resend_email'),
            reverse('api_v1:register'),
            reverse('api_v1:resend-email'),
            reverse('api_v1:verify-email')
            
            
        ]
        if not request.user.is_authenticated and request.path not in allowed_paths:
            return redirect('login')
        return self.get_response(request)