"""Экспорт каталога книг для генерации эмбеддингов в Colab."""

import csv
import os
import sys
from pathlib import Path

import django

# Настройка Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'coursework.settings')
PROJECT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_DIR))
django.setup()

from books.models import Book

with (PROJECT_DIR / 'books_export.csv').open('w', newline='', encoding='utf-8') as f:
    writer = csv.writer(f)
    writer.writerow(['id', 'title', 'author', 'genres', 'release_year', 'description'])
    books = (
        Book.objects
        .select_related('author')
        .prefetch_related('genres')
        .order_by('id')
    )
    for book in books:
        # Стабильный порядок делает повторную генерацию воспроизводимой и
        # не позволяет менять текст книги из-за порядка жанров.
        genres = ', '.join(
            genre.genre for genre in book.genres.all().order_by('genre')
        )
        writer.writerow([
            book.id,
            book.title,
            book.author.fullname,
            genres,
            book.release_year or '',
            book.description or '',
        ])

print('Export completed: books_export.csv, books: {}'.format(Book.objects.count()))
