from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include

from users import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('books.urls')),
    path('auth/', include('django.contrib.auth.urls')),
    path('registration/', views.UserRegistrationView.as_view(), name='registration'),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
