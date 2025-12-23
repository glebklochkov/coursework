from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404
from django.views.generic import ListView, DetailView

from books.models import Book


class ListViewMixin:
    model = Book
    context_object_name = 'book_list'
    paginate_by = 4
    template_name = 'books/book_list.html'


class BooksListView(ListView):
    model = Book
    context_object_name = 'book_list'
    paginate_by = 8
    template_name = 'books/book_list.html'  # можно переопределять в url

    def get_queryset(self):
        queryset = Book.objects.all()

        genre = self.kwargs.get("genre_slug")
        if genre:
            queryset = queryset.filter(genres__slug=genre)

        author = self.kwargs.get("author_id")
        if author:
            queryset = queryset.filter(author__id=author)

        sort = self.request.GET.get("sort")
        if sort:
            queryset = queryset.order_by(sort)
        else:
            queryset = queryset.order_by("title")


        if self.request.resolver_match.url_name == "saved_books":
            user_id = self.kwargs.get('pk')
            user = get_object_or_404(get_user_model(), id=user_id)
            queryset = user.saved_books.all()
        elif self.request.resolver_match.url_name == "read_books":
            user_id = self.kwargs.get('pk')
            user = get_object_or_404(get_user_model(), id=user_id)
            queryset = user.read_books.all()

        return queryset


# class MainPageListView(ListViewMixin, ListView):
#     template_name = 'books/index.html'
#
#     def get_queryset(self):
#         queryset = Book.objects.all().order_by('title')
#         return queryset
#
#
# class GenreListView(ListViewMixin, ListView):
#
#     def get_queryset(self):
#         queryset = Book.objects.filter(genres__slug=self.kwargs['genre_slug']).order_by('title')
#         return queryset
#
#
# class AuthorListView(ListViewMixin, ListView):
#
#     def get_queryset(self):
#         queryset = Book.objects.filter(author__id=int(self.kwargs['author_id'])).order_by('title')
#         return queryset
#
#
class BookDetailView(DetailView):
    model = Book
    template_name = 'books/book_detail.html'
    context_object_name = 'book'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        book = self.get_object()

        context["is_saved"] = user.is_authenticated and book in user.saved_books.all()
        context["is_read"] = user.is_authenticated and book in user.read_books.all()
        return context


@login_required
def toggle_saved(request, book_id):
    book = get_object_or_404(Book, id=book_id)
    user = request.user

    if book in user.saved_books.all():
        user.saved_books.remove(book)
        status = "removed"
    else:
        user.saved_books.add(book)
        status = "added"

    return JsonResponse({"status": status})


@login_required
def toggle_read(request, book_id):
    book = get_object_or_404(Book, id=book_id)
    user = request.user

    if book in user.read_books.all():
        user.read_books.remove(book)
        status = "removed"
    else:
        user.read_books.add(book)
        status = "added"

    return JsonResponse({"status": status})
