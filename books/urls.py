from django.urls import path, include

from books import views
from books.views import toggle_saved, toggle_read

app_name = 'books'

urlpatterns = [
    path('', views.BooksListView.as_view(), name='index'),
    path('book/<int:pk>/', views.BookDetailView.as_view(), name='detail'),
    path('book/<int:pk>/edit/', views.BookEdit.as_view(), name='book_edit'),
    path('genre/<str:genre_slug>/', views.BooksListView.as_view(), name='genre'),
    path('author/<int:author_id>/', views.BooksListView.as_view(), name='author'),
    path('toggle_saved/<int:book_id>/', toggle_saved, name='toggle_saved'),
    path('toggle_read/<int:book_id>/', toggle_read, name='toggle_read'),
]