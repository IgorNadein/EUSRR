# backend/communications/urls.py

from django.urls import path

from . import api_views, views

app_name = "communications"

urlpatterns = [
    # UI Views
    path("chats/", views.ChatListView.as_view(), name="chat_list"),
    path("chats/<int:pk>/", views.ChatDetailView.as_view(), name="chat_detail"),
    path(
        "chats/start/<int:employee_pk>/",
        views.start_private_chat,
        name="start_private_chat"
    ),
    path("chats/<int:pk>/mark-read/", views.chat_mark_read, name="chat_mark_read"),
    path(
        "start/private/<int:employee_pk>/",
        views.start_private_chat,
        name="start_private_chat"
    ),
    
    # API Endpoints
    # Chat management
    path("api/chat/create/", api_views.create_chat, name="api_create_chat"),
    path(
        "api/chat/<int:chat_id>/update/",
        api_views.update_chat,
        name="api_update_chat"
    ),
    path(
        "api/chat/<int:chat_id>/pin/",
        api_views.pin_chat,
        name="api_pin_chat"
    ),
    path(
        "api/chat/<int:chat_id>/notifications/",
        api_views.set_chat_notifications,
        name="api_chat_notifications"
    ),
    path(
        "api/announcement/<int:chat_id>/block/",
        api_views.block_announcement,
        name="api_block_announcement"
    ),
    path(
        "api/announcement/<int:chat_id>/unblock/",
        api_views.unblock_announcement,
        name="api_unblock_announcement"
    ),
    
    # Message actions
    path(
        "api/message/<int:message_id>/edit/",
        api_views.edit_message,
        name="api_edit_message"
    ),
    path(
        "api/message/<int:message_id>/delete/",
        api_views.delete_message,
        name="api_delete_message"
    ),
    path(
        "api/message/<int:message_id>/react/",
        api_views.add_reaction,
        name="api_add_reaction"
    ),
    path(
        "api/message/<int:message_id>/unreact/",
        api_views.remove_reaction,
        name="api_remove_reaction"
    ),
    path(
        "api/message/<int:message_id>/pin/",
        api_views.pin_message,
        name="api_pin_message"
    ),
    
    # Attachments
    # Основной endpoint для загрузки сообщений с файлами находится в api/v1
    path(
        "api/attachment/upload/",
        api_views.upload_attachment,
        name="api_upload_attachment"
    ),
    
    # Forward & Reply
    path(
        "api/message/<int:message_id>/forward/",
        api_views.forward_message,
        name="api_forward_message"
    ),
    path(
        "api/message/<int:message_id>/reply/",
        api_views.reply_to_message,
        name="api_reply_message"
    ),
    
    # Membership
    path(
        "api/chat/<int:chat_id>/member/add/",
        api_views.add_member,
        name="api_add_member"
    ),
    path(
        "api/chat/<int:chat_id>/member/remove/",
        api_views.remove_member,
        name="api_remove_member"
    ),
]
