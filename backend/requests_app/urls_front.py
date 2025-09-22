# urls.py
from django.urls import path
from .views_front import RequestsView

app_name = "requests"

urlpatterns = [
    path("", RequestsView.as_view(), name="request_list"),
]
