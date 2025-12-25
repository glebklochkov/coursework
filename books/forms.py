from django import forms

from books.models import Book, Genre


class BookForm(forms.ModelForm):
    class Meta:
        model = Book
        fields = ('title', 'author', 'release_year', 'genres', 'description', 'poster')
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control book-title-input'
            }),
            'author': forms.Select(attrs={
                'class': 'form-control author-select'
            }),
            'release_year': forms.NumberInput(attrs={
                'class': 'form-control year-input',
                'min': 0,
                'max': 2026
            }),
            'genres': forms.SelectMultiple(attrs={
                'class': 'form-control genres-select'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control description-input',
                'rows': 8
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['genres'].queryset = Genre.objects.order_by('genre')