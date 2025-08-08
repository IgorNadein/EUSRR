from django.urls import path

from . import views

app_name = "feed"

urlpatterns = [
    path("", views.feed_list, name="feed_list"),
    path("departments/<int:pk>/", views.department_feed, name="department_feed"),
    path("employees/<int:pk>/", views.employee_feed, name="employee_feed"),
    path("post/new/", views.post_create, name="post_create"),
    path("post/<int:pk>/", views.post_detail, name="post_detail"),
    path("post/<int:pk>/edit/", views.post_update, name="post_update"),
    path("post/<int:pk>/delete/", views.post_delete, name="post_delete"),
    path("post/<int:pk>/pin/", views.pin_post, name="pin_post"),
    path("comment/<int:pk>/edit/", views.comment_update, name="comment_update"),
    path("comment/<int:pk>/delete/", views.comment_delete, name="comment_delete"),
]
