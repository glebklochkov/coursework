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

    class Meta:
        model = Book
        fields = ['author', 'genre']

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
