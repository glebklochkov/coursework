import requests
import time
from django.core.management.base import BaseCommand
from django.core.files.base import ContentFile
from books.models import Book
from django.utils.text import slugify


class Command(BaseCommand):
    help = "Поиск и загрузка недостающих обложек через Google Books API"

    def handle(self, *args, **options):
        # только те книги, у которых нет обложки
        books_without_poster = Book.objects.filter(poster__in=['', None])
        self.stdout.write(f"Найдено книг без обложки: {books_without_poster.count()}")

        for book in books_without_poster:
            self.stdout.write(self.style.NOTICE(f"Ищем обложку для: {book.title} ({book.author.fullname})"))

            search_query = f"{book.title} {book.author.fullname}"
            url = "https://www.googleapis.com/books/v1/volumes"
            params = {
                "q": search_query,
                "maxResults": 1,
                "langRestrict": "ru"  # приоритет русским изданиям
            }

            try:
                response = requests.get(url, params=params, timeout=10)
                if response.status_code != 200:
                    continue

                data = response.json()
                items = data.get("items", [])

                if not items:
                    self.stdout.write(self.style.WARNING(f"Не найдено в Google Books: {book.title}"))
                    continue

                volume_info = items[0].get("volumeInfo", {})
                image_links = volume_info.get("imageLinks", {})

                image_url = image_links.get("thumbnail") or image_links.get("smallThumbnail")

                if image_url:
                    image_url = image_url.replace("http://", "https://")

                    img_resp = requests.get(image_url, timeout=10)
                    if img_resp.status_code == 200:
                        # Проверка на размер
                        if len(img_resp.content) > 1000:
                            file_name = f"{book.id}_{slugify(book.title, allow_unicode=True)}.jpg"
                            book.poster.save(file_name, ContentFile(img_resp.content), save=True)
                            self.stdout.write(self.style.SUCCESS(f"Успешно добавлена обложка для: {book.title}"))
                        else:
                            self.stdout.write(self.style.WARNING(f"Слишком маленькое изображение для: {book.title}"))

                time.sleep(1)

            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Ошибка при обработке {book.title}: {e}"))

        self.stdout.write(self.style.SUCCESS("Обработка завершена!"))