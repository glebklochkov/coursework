from django.contrib.auth.models import AbstractUser
from django.db import models
from books.models import Book


class User(AbstractUser):
    saved_books = models.ManyToManyField(
        Book, blank=True, related_name='users_saved', verbose_name='Избранные книги'
    )
    read_books = models.ManyToManyField(
        Book, blank=True, related_name='users_read', verbose_name='Прочитанные книги'
    )

    class Meta:
        verbose_name = 'пользователь'
        verbose_name_plural = 'Пользователи'

    def __str__(self):
        return self.username