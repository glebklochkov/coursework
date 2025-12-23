from django.urls import path, include

from books import views

app_name = 'books'

urlpatterns = [
    path('', views.MainPageListView.as_view(), name='index'),
    path('book/<int:pk>', views.BookDetailView.as_view(), name='detail'),
    path('genre/<slug:genre_slug>/', views.GenreListView.as_view(), name='genre'),
    path('author/<int:author_id>/', views.AuthorListView.as_view(), name='author'),
]