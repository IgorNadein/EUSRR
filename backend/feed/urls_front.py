from django.urls import path

from . import views_front

app_name = "feed"

urlpatterns = [
    path("", views_front.feed_list, name="feed_list"),
    path("departments/<int:pk>/", views_front.department_feed, name="department_feed"),
    path("employees/<int:pk>/", views_front.employee_feed, name="employee_feed"),
    path("post/new/", views_front.post_create, name="post_create"),
    path("post/<int:pk>/", views_front.post_detail, name="post_detail"),
    path("post/<int:pk>/edit/", views_front.post_update, name="post_update"),
    path("post/<int:pk>/delete/", views_front.post_delete, name="post_delete"),
    path("post/<int:pk>/pin/", views_front.pin_post, name="pin_post"),
    path("post/<int:pk>/like/", views_front.toggle_like, name="toggle_like"),
    path("comment/<int:pk>/edit/", views_front.comment_update, name="comment_update"),
    path("comment/<int:pk>/delete/", views_front.comment_delete, name="comment_delete"),
]
