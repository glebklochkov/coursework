# books/filters.py
import django_filters
from django import forms
from django.shortcuts import get_object_or_404

from books.models import Author, Book, Genre


class BookFilter(django_filters.FilterSet):
    author = django_filters.ModelMultipleChoiceFilter(
        queryset=Author.objects.all().order_by('shortname'),
        field_name='author',               # поле в модели Book
        widget=forms.CheckboxSelectMultiple,  # именно чекбоксы
        label='Авторы',
    )

    genre = django_filters.ModelMultipleChoiceFilter(
        queryset=Genre.objects.all().order_by('genre'),
        field_name='genres',
        widget=forms.CheckboxSelectMultiple,
        label='Жанры'
    )

    user_rating = django_filters.MultipleChoiceFilter(
        method='filter_by_user_rating',
        choices=[
            (1, '1'),
            (2, '2'),
            (3, '3'),
            (4, '4'),
            (5, '5'),
        ],
        # widget=forms.Select(attrs={'class': 'form-select form-select-sm'}),
        widget=forms.CheckboxSelectMultiple,
        label = 'Мои оценки',
    )

    class Meta:
        model = Book
        fields = ['author', 'genre', 'user_rating']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if 'genre_slug' in self.request.resolver_match.kwargs:
            genre = get_object_or_404(Genre, slug=self.request.resolver_match.kwargs['genre_slug'])
            self.filters['genre'].field.queryset = Genre.objects.filter(id=genre.id)  # только этот жанр
            self.filters['genre'].field.widget.attrs['disabled'] = 'disabled'  # заблокировать чекбокс

        if 'author_id' in self.request.resolver_match.kwargs:
            author = get_object_or_404(Author, id=self.request.resolver_match.kwargs['author_id'])
            self.filters['author'].field.queryset = Author.objects.filter(id=author.id)
            self.filters['author'].field.widget.attrs['disabled'] = 'disabled'

        if '/recommendations/' in self.request.path:
            self.filters['user_rating'].field.widget.attrs['disabled'] = 'disabled'

    def filter_by_user_rating(self, queryset, name, value):
        if value and self.request.user.is_authenticated:
            return queryset.filter(
                ratings__user=self.request.user,
                ratings__value__in=value
            ).distinct()
        return queryset
