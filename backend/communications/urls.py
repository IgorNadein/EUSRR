# backend/communications/urls.py

from django.urls import path

from . import views

app_name = "communications"

urlpatterns = [
    path("chats/", views.ChatListView.as_view(), name="chat_list"),
    path("chats/<int:pk>/", views.ChatDetailView.as_view(), name="chat_detail"),
    path("chats/start/<int:employee_pk>/", views.start_private_chat, name="start_private_chat"),
    path("chats/<int:pk>/mark-read/", views.chat_mark_read, name="chat_mark_read"),
    path("start/private/<int:employee_pk>/", views.start_private_chat, name="start_private_chat"),


]
