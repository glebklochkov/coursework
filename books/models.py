from django.db import models


class Author(models.Model):
    shortname = models.CharField(verbose_name='Фамилия', max_length=50)
    fullname = models.CharField(verbose_name='Полное имя', max_length=200)

    class Meta:
        verbose_name = 'автор'
        verbose_name_plural = 'Авторы'

    def __str__(self):
        return self.fullname


class Genre(models.Model):
    genre = models.CharField(verbose_name='Жанр', max_length=50)
    slug = models.SlugField(verbose_name='Идентификатор', unique=True)

    class Meta:
        verbose_name = 'жанр',
        verbose_name_plural = 'Жанры'

    def __str__(self):
        return self.genre



class Book(models.Model):
    title = models.CharField(verbose_name='Название', max_length=200)
    description = models.TextField('Описание')
    release_year = models.IntegerField('Год выхода')
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
