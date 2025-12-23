from django.shortcuts import render
from django.views.generic import ListView, DetailView

from books.models import Book


class ListViewMixin:
    model = Book
    context_object_name = 'book_list'
    paginate_by = 8
    template_name = 'books/book_list.html'


class MainPageListView(ListViewMixin, ListView):
    template_name = 'books/index.html'

    def get_queryset(self):
        queryset = Book.objects.all().order_by('title')
        return queryset


class GenreListView(ListViewMixin, ListView):

    def get_queryset(self):
        queryset = Book.objects.filter(genres__slug=self.kwargs['genre_slug']).order_by('title')
        return queryset


class AuthorListView(ListViewMixin, ListView):

    def get_queryset(self):
        queryset = Book.objects.filter(author__id=int(self.kwargs['author_id'])).order_by('title')
        return queryset


class BookDetailView(DetailView):
    model = Book
    template_name = 'books/book_detail.html'
    context_object_name = 'book'
