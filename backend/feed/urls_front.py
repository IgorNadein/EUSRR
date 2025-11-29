from django.urls import path

from . import views_front

app_name = "feed"

urlpatterns = [
    path("", views_front.feed_list, name="feed_list"),
    path("departments/<int:pk>/", views_front.department_feed, name="department_feed"),
    path("employees/<int:pk>/", views_front.employee_feed, name="employee_feed"),
    path("post/<int:pk>/", views_front.post_detail, name="post_detail"),
    path("post/<int:pk>/pin/", views_front.pin_post, name="pin_post"),
    path("post/<int:pk>/like/", views_front.toggle_like, name="toggle_like"),
]
