# books/filters.py
import django_filters
from django import forms

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
