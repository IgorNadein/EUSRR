# api/auth/views.py
from rest_framework_simplejwt.views import TokenObtainPairView

from .serializers import PhoneOrEmailTokenObtainPairSerializer


class PhoneOrEmailTokenObtainPairView(TokenObtainPairView):
    serializer_class = PhoneOrEmailTokenObtainPairSerializer


