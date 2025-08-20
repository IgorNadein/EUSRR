# backend\employees\authentication.py
from django.contrib.auth.backends import ModelBackend

from .models import Employee


class EmailOrPhoneBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        if username is None:
            username = kwargs.get("username")

        try:
            # Проверяем, email ли это
            if "@" in username:
                user = Employee.objects.get(email=username)
            else:
                # Иначе phone
                user = Employee.objects.get(phone_number=username)
        except Employee.DoesNotExist:
            return None

        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None

    def get_user(self, user_id):
        try:
            return Employee.objects.get(pk=user_id)
        except Employee.DoesNotExist:
            return None
