from django.urls import path, include

from books import views
from books.views import toggle_saved, toggle_read

app_name = 'books'

urlpatterns = [
    path('', views.BooksListView.as_view(), name='index'),
    path('book/create/', views.BookCreateView.as_view(), name='book_create'),
    path('book/<int:pk>/', views.BookDetailView.as_view(), name='detail'),
    path('book/<int:pk>/edit/', views.BookEdit.as_view(), name='book_edit'),
    path('book/<int:pk>/delete/', views.BookDeleteView.as_view(), name='book_delete'),
    path('genre/create/', views.GenreCreateView.as_view(), name='genre_create'),
    path('genre/<str:genre_slug>/', views.BooksListView.as_view(), name='genre'),
    path('genre/<str:slug>/edit/', views.GenreEditView.as_view(), name='genre_edit'),
    path('genre/<str:slug>/delete/', views.GenreDeleteView.as_view(), name='genre_delete'),
    path('author/create/', views.AuthorCreateView.as_view(), name='author_create'),
    path('author/<int:author_id>/', views.BooksListView.as_view(), name='author'),
    path('author/<int:pk>/edit/', views.AuthorEditView.as_view(), name='author_edit'),
    path('author/<int:pk>/delete/', views.AuthorDeleteView.as_view(), name='author_delete'),
    path('toggle_saved/<int:book_id>/', toggle_saved, name='toggle_saved'),
    path('toggle_read/<int:book_id>/', toggle_read, name='toggle_read'),
    path('rate/', views.rate_book, name='rate_book'),
]