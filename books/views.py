from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404
from django.urls import reverse_lazy, reverse
from django.views.generic import ListView, DetailView, UpdateView, DeleteView, CreateView

from books.forms import BookForm, AuthorForm, GenreForm
from books.models import Book, Author, Genre


class BooksListView(ListView):
    model = Book
    context_object_name = 'book_list'
    paginate_by = 40
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

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.kwargs.get("genre_slug"):
            genre = get_object_or_404(Genre, slug=self.kwargs.get('genre_slug'))
            context['genre'] = genre
        elif self.kwargs.get("author_id"):
            author = get_object_or_404(Author, id=self.kwargs.get('author_id'))
            context['author'] = author
        return context


class BookMixin:
    model = Book
    context_object_name = 'book'


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


class BookCreateView(BookMixin, CreateView):
    form_class = BookForm
    template_name = 'books/book_edit_form.html'

    def get_success_url(self):
        return reverse_lazy('books:detail', kwargs={'pk': self.object.pk})


class BookEdit(UpdateView):
    model = Book
    form_class = BookForm
    context_object_name = 'book'
    template_name = 'books/book_edit_form.html'

    def get_success_url(self):
        return reverse_lazy('books:detail', kwargs={'pk': self.object.pk})


class BookDeleteView(DeleteView):
    model = Book
    context_object_name = 'book'
    template_name = 'books/book_delete.html'

    def get_success_url(self):
        return reverse_lazy('books:index')


class AuthorMixin:
    model = Author
    context_object_name = 'author'
    template_name = 'books/author_form.html'


class AuthorCreateView(AuthorMixin, CreateView):
    form_class = AuthorForm

    def get_success_url(self):
        return reverse_lazy('books:author', kwargs={'author_id': self.object.pk})


class AuthorEditView(AuthorMixin, UpdateView):
    form_class = AuthorForm

    def get_success_url(self):
        return reverse_lazy('books:author', kwargs={'author_id': self.object.pk})


class AuthorDeleteView(AuthorMixin, DeleteView):
    def get_success_url(self):
        return reverse_lazy('books:index')


class GenreMixin:
    model = Genre
    context_object_name = 'genre'
    template_name = 'books/genre_form.html'


class GenreCreateView(GenreMixin, CreateView):
    form_class = GenreForm

    def get_success_url(self):
        return reverse_lazy('books:genre', kwargs={'genre_slug': self.object.slug})


class GenreEditView(GenreMixin, UpdateView):
    form_class = GenreForm

    def get_success_url(self):
        return reverse_lazy('books:genre', kwargs={'genre_slug': self.object.slug})


class GenreDeleteView(GenreMixin, DeleteView):
    def get_success_url(self):
        return reverse_lazy('books:index')


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
