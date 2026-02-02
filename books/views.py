from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404
from django.urls import reverse_lazy, reverse
from django.views.decorators.http import require_POST
from django.views.generic import ListView, DetailView, UpdateView, DeleteView, CreateView
from django_filters.views import FilterView

from books.forms import BookForm, AuthorForm, GenreForm
from books.management.services.filters import BookFilter
from books.management.services.recommendations import recommend_books
from books.models import Book, Author, Genre, BookRating


class BooksListView(FilterView):
    model = Book
    context_object_name = 'book_list'
    paginate_by = 40
    template_name = 'books/book_list.html'
    filterset_class = BookFilter

    # def get_filterset_kwargs(self, filterset_class):
    #     kwargs = super().get_filterset_kwargs(filterset_class)
    #
    #     # Передаём именно тот queryset, который уже сформирован в get_queryset()
    #     # (это уже закладки, прочитанные, рекомендации и т.д.)
    #     kwargs['queryset'] = self.get_queryset()
    #
    #     return kwargs

    def get_queryset(self):
        if self.request.resolver_match.url_name == 'recommendations':
            sort = self.request.GET.get("sort", "score")
            direction = self.request.GET.get("dir", "desc")
            return recommend_books(self.request.user, sort=sort, direction=direction)

        queryset = Book.objects.all()

        if self.request.resolver_match.url_name == "saved_books":
            user_id = self.kwargs.get('pk')
            user = get_object_or_404(get_user_model(), id=user_id)
            queryset = user.saved_books.all()
        elif self.request.resolver_match.url_name == "read_books":
            user_id = self.kwargs.get('pk')
            user = get_object_or_404(get_user_model(), id=user_id)
            queryset = user.read_books.all()
        elif self.request.resolver_match.url_name == 'rated_books':
            user_id = self.kwargs.get('pk')
            user = get_object_or_404(get_user_model(), id=user_id)
            queryset = user.rated_books.all()

        # Сортировка по GET (для обычных списков)
        sort = self.request.GET.get("sort", "title")
        direction = self.request.GET.get("dir", "asc")
        allowed_sorts = {
            "title": "title",
            "release_year": "release_year",
        }
        sort_field = allowed_sorts.get(sort, "title")
        if direction == "desc":
            sort_field = f"-{sort_field}"
        queryset = queryset.order_by(sort_field)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["filter"] = self.filterset

        if self.kwargs.get("genre_slug"):
            genre = get_object_or_404(Genre, slug=self.kwargs.get('genre_slug'))
            context['genre'] = genre
        elif self.kwargs.get("author_id"):
            author = get_object_or_404(Author, id=self.kwargs.get('author_id'))
            context['author'] = author

        if self.request.resolver_match.url_name == 'recommendations':
            current_sort = self.request.GET.get("sort", "score")
            current_dir = self.request.GET.get("dir", "desc")
            context[
                "current_sort"] = current_sort
            context["current_dir"] = current_dir
        else:
            current_sort = self.request.GET.get("sort", "title")
            current_dir = self.request.GET.get("dir", "asc")
            context["current_sort"] = current_sort
            context["current_dir"] = current_dir

        # Вычисляем следующее направление для каждой кнопки
        context["title_next_dir"] = "desc" if current_sort == "title" and current_dir == "asc" else "asc"
        context["year_next_dir"] = "desc" if current_sort == "release_year" and current_dir == "asc" else "asc"
        context["score_next_dir"] = "desc" if current_sort == "score" and current_dir == "asc" else "asc"

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

        if user.is_authenticated:
            rating = BookRating.objects.filter(
                book=book,
                user=user
            ).first()
            context["user_rating"] = rating.value if rating else 0

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


@require_POST
@login_required
def rate_book(request):
    book_id = request.POST.get('book_id')
    value = int(request.POST.get('value'))
    user = request.user

    book = get_object_or_404(Book, id=book_id)

    # Снять оценку
    if value == 0:
        BookRating.objects.filter(book=book, user=user).delete()
        user.rated_books.remove(book)

        return JsonResponse({
            'success': True,
            'rating': 0,
            'avg': book.average_rating(),
            'count': book.ratings_count()
        })

    # Поставить / изменить оценку
    if value < 1 or value > 5:
        return JsonResponse({'error': 'Invalid rating'}, status=400)

    rating, created = BookRating.objects.update_or_create(
        book=book,
        user=user,
        defaults={'value': value}
    )

    user.rated_books.add(book)

    return JsonResponse({
        'success': True,
        'rating': value,
        'avg': book.average_rating(),
        'count': book.ratings_count()
    })
