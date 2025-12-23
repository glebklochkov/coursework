from django.urls import path

from users import views
from users.views import UserAccountView

app_name = 'users'

urlpatterns = [
    path('profile/<int:pk>', UserAccountView.as_view(), name='profile')
]