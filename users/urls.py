from django.urls import path

from books.views import BooksListView
from users import views
from users.views import UserAccountView, AccountSettingsView

app_name = 'users'

urlpatterns = [
    path('profile/<int:pk>/', UserAccountView.as_view(), name='profile'),
    path('profile/<int:pk>/settings/', AccountSettingsView.as_view(), name='profile_settings'),
    path('profile/<int:pk>/saved_books/', BooksListView.as_view(), name="saved_books"),
    path('profile/<int:pk>/read_books/', BooksListView.as_view(), name="read_books"),
    path('profile/<int:pk>/rated_books/', BooksListView.as_view(), name="rated_books"),
]