from django.contrib.auth.models import AbstractUser
from django.db import models
from books.models import Book
from django.utils.translation import gettext_lazy as _


class User(AbstractUser):
    avatar = models.ImageField(verbose_name='Аватар', upload_to='users-avatars', blank=True)
    email = models.EmailField(_("email address"))
    saved_books = models.ManyToManyField(
        Book, blank=True, related_name='users_saved', verbose_name='Избранные книги'
    )
    read_books = models.ManyToManyField(
        Book, blank=True, related_name='users_read', verbose_name='Прочитанные книги'
    )
    rated_books = models.ManyToManyField(
        Book, blank=True, related_name='users_rated', verbose_name='Оценённые книги'
    )

    class Meta:
        verbose_name = 'пользователь'
        verbose_name_plural = 'Пользователи'

    def __str__(self):
        return self.username