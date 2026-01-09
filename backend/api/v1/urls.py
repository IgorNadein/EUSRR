from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .calendar.views import CalendarEventsViewSet
from .employees.views import (DepartmentRoleViewSet, DepartmentViewSet,
                              EmployeeActionViewSet, EmployeeViewSet,
                              GroupViewSet, PositionViewSet,
                              RegisterAPIView, ResendEmailAPIView,
                              SkillViewSet, VerifyEmailAPIView)
from .feed.views import CommentViewSet, PostViewSet
from .documents.views import DocumentViewSet
from .requests_app.views import RequestViewSet
from .communications.views import (
    add_reaction,
    bulk_delete_messages,
    create_chat,
    delete_message,
    edit_message,
    forward_messages,
    get_available_reactions,
    get_message_reactions,
    get_user_chats,
    load_chat_messages,
    pin_chat,
    remove_reaction,
    toggle_chat_notifications,
    upload_message_with_attachments,
)
from .communications.poll_views import (
    close_poll,
    create_poll,
    get_poll_results,
    vote_poll,
)

app_name = "v1"

router = DefaultRouter()

router.register(r"calendar/events", CalendarEventsViewSet, basename="events")

router.register(r"documents", DocumentViewSet, basename="documents")

router.register(r"requests", RequestViewSet, basename="request")

router.register(r"departments", DepartmentViewSet, basename="departments")
router.register(r"employees", EmployeeViewSet, basename="employees")
router.register(
    r"employee-actions",
    EmployeeActionViewSet,
    basename="employee-actions",
)
router.register(r"positions", PositionViewSet, basename="positions")
router.register(
    r"department-roles",
    DepartmentRoleViewSet,
    basename="department-roles",
)
router.register(r"skills", SkillViewSet, basename="skills")
router.register(r"posts", PostViewSet, basename="posts")
router.register(r"comments", CommentViewSet, basename="comments")
router.register(r"groups", GroupViewSet, basename="groups")


urlpatterns = [
    path("auth/register/", RegisterAPIView.as_view(), name="register"),
    path(
        "auth/resend-email/",
        ResendEmailAPIView.as_view(),
        name="resend-email",
    ),
    path(
        "auth/verify-email/",
        VerifyEmailAPIView.as_view(),
        name="verify-email",
    ),
    path(
        "communications/chats/",
        get_user_chats,
        name="user_chats"
    ),
    path(
        "communications/chats/create/",
        create_chat,
        name="create_chat"
    ),
    path(
        "communications/upload-message/",
        upload_message_with_attachments,
        name="upload_message"
    ),
    path(
        "communications/chats/<int:pk>/messages/",
        load_chat_messages,
        name="chat_messages",
    ),
    path(
        "communications/chats/<int:chat_id>/pin/",
        pin_chat,
        name="pin_chat"
    ),
    path(
        "communications/chats/<int:chat_id>/notifications/",
        toggle_chat_notifications,
        name="toggle_chat_notifications"
    ),
    path(
        "communications/messages/<int:message_id>/reactions/",
        get_message_reactions,
        name="message_reactions"
    ),
    path(
        "communications/reactions/available/",
        get_available_reactions,
        name="available_reactions"
    ),
    path(
        "communications/messages/<int:message_id>/react/",
        add_reaction,
        name="add_reaction"
    ),
    path(
        "communications/messages/<int:message_id>/unreact/",
        remove_reaction,
        name="remove_reaction"
    ),
    path(
        "communications/messages/<int:message_id>/edit/",
        edit_message,
        name="edit_message"
    ),
    path(
        "communications/messages/<int:message_id>/delete/",
        delete_message,
        name="delete_message"
    ),
    path(
        "communications/messages/forward/",
        forward_messages,
        name="forward_messages"
    ),
    path(
        "communications/messages/bulk-delete/",
        bulk_delete_messages,
        name="bulk_delete_messages"
    ),
    # Poll endpoints
    path(
        "communications/polls/create/",
        create_poll,
        name="create_poll"
    ),
    path(
        "communications/polls/<int:poll_id>/vote/",
        vote_poll,
        name="vote_poll"
    ),
    path(
        "communications/polls/<int:poll_id>/close/",
        close_poll,
        name="close_poll"
    ),
    path(
        "communications/polls/<int:poll_id>/results/",
        get_poll_results,
        name="poll_results"
    ),
    
    # Notifications API
    path("notifications/", include("api.v1.notifications.urls")),
    
    path("", include(router.urls)),
]
