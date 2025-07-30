from django.contrib import admin
from django.urls import include, path, reverse_lazy
from django.views.generic.edit import CreateView
from users.forms import RegistrationForm
from users.views import profile, avatar_remove
from django.conf.urls.static import static
from django.conf import settings


urlpatterns = [
    path('admin/', admin.site.urls),
    path('auth/', include('django.contrib.auth.urls')),
    path('auth/register/', CreateView.as_view(
        template_name='registration/register.html',
        form_class=RegistrationForm,
        success_url=reverse_lazy('profile')
    ), name='register'),
    path('avatar/remove/', avatar_remove, name='avatar_remove'),
    path('calendar/', include('calendar_app.urls', namespace='calendar')),
    path('documents/', include('documents.urls', namespace='documents')),
    path('', profile, name='profile'),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
