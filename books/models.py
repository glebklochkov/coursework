from django.core.validators import RegexValidator
from django.db import models
from django.db.migrations import RenameModel
from slugify import slugify


cyrillic_slug_validator = RegexValidator(
    regex=r'^[\w-а-яА-ЯёЁ]+$',
    message='Разрешены буквы, цифры, дефис и подчёркивание'
)

class Author(models.Model):
    fullname = models.CharField(verbose_name='Полное имя', max_length=200)
    shortname = models.CharField(verbose_name='Фамилия', max_length=50, blank=True)

    class Meta:
        verbose_name = 'автор'
        verbose_name_plural = 'Авторы'

    def save(self, *args, **kwargs):
        if not self.shortname and self.fullname:
            author_name_split = self.fullname.split()
            shortname_generated = ""
            for i in range(0, len(author_name_split)):
                if i != len(author_name_split) - 1:
                    shortname_generated += author_name_split[i][0] + '. '
                else:
                    shortname_generated += author_name_split[i]
            self.shortname = shortname_generated

        super().save(*args, **kwargs)

    def __str__(self):
        return self.fullname


class Genre(models.Model):
    genre = models.CharField(verbose_name='Жанр', max_length=50)
    slug = models.SlugField(verbose_name='Слаг', unique=True, blank=True, allow_unicode=True)

    class Meta:
        verbose_name = 'жанр',
        verbose_name_plural = 'Жанры'

    def save(self, *args, **kwargs):
        if not self.slug and self.genre:
            slug_generated = slugify(self.genre, allow_unicode=True)
            self.slug = slug_generated

        super().save(*args, **kwargs)

    def __str__(self):
        return self.genre



class Book(models.Model):
    title = models.CharField(verbose_name='Название', max_length=200)
    description = models.TextField('Описание', blank=True, null=True)
    release_year = models.IntegerField('Год выхода', blank=True, null=True)
    is_published = models.BooleanField('Опубликовано', default=True)
    poster = models.ImageField('Обложка', upload_to='books-posters', blank=True)
    author = models.ForeignKey(
        Author,
        verbose_name='Автор',
        on_delete=models.CASCADE
    )
    genres = models.ManyToManyField(
        Genre,
        verbose_name='Жанры',
        related_name='books'
    )

    class Meta:
        verbose_name = 'книга'
        verbose_name_plural = 'Книги'

    def __str__(self):
        return self.title
