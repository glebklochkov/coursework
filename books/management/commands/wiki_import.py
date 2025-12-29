import requests
import time
import re
import hashlib
from datetime import datetime
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from books.models import Book, Author, Genre
from slugify import slugify
from urllib.parse import unquote

WIKIDATA_SPARQL_URL = "https://query.wikidata.org/sparql"
WIKIPEDIA_API_URL = "https://ru.wikipedia.org/w/api.php"

AUTHOR_MAP = {
    # "Александр Сергеевич Пушкин": "Q7200",
    # "Фёдор Михайлович Достоевский": "Q991",
    # "Михаил Афанасьевич Булгаков": "Q835",
    "Александр Дюма": "Q38337",
    # "Николай Васильевич Гоголь": "Q43718",
    # "Лев Николаевич Толстой": "Q7243",
    # "Антон Павлович Чехов": "Q5685",
    # "Иван Сергеевич Тургенев": "Q42831",
    # "Артур Конан Дойл": "Q35610",
}

def get_books_from_wikidata(author_qid):
    query = f"""
    SELECT ?book ?bookLabel ?description ?pubDate ?genre ?genreLabel ?image ?wikiTitle WHERE {{
      ?book wdt:P31/wdt:P279* wd:Q7725634 ;
            wdt:P50 wd:{author_qid} .

      OPTIONAL {{ ?book wdt:P577 ?pubDate . }}
      OPTIONAL {{ ?book wdt:P136 ?genre . }}
      OPTIONAL {{ ?book wdt:P18 ?image . }}
      OPTIONAL {{ ?book schema:description ?description FILTER(LANG(?description) = "ru") . }}

      OPTIONAL {{
        ?article schema:about ?book ;
                 schema:isPartOf <https://ru.wikipedia.org/> .
        BIND(REPLACE(STR(?article), "https://ru.wikipedia.org/wiki/", "") AS ?wikiTitle)
      }}

      SERVICE wikibase:label {{ 
        bd:serviceParam wikibase:language "[AUTO_LANGUAGE],ru,en" .
      }}
    }} LIMIT 200
    """

    headers = {"User-Agent": "BookImporter/1.0 (your-email@example.com)"}
    params = {"query": query, "format": "json"}

    resp = requests.get(WIKIDATA_SPARQL_URL, params=params, headers=headers)
    if resp.status_code != 200:
        return []
    return resp.json().get("results", {}).get("bindings", [])

def get_wikipedia_extract(wiki_title):
    if not wiki_title:
        return ""

    decoded = unquote(wiki_title)

    headers = {"User-Agent": "BookImporter/1.0"}

    # --- 1) REST SUMMARY ---
    url = f"https://ru.wikipedia.org/api/rest_v1/page/summary/{decoded}"
    resp = requests.get(url, headers=headers)

    text = ""
    if resp.status_code == 200:
        data = resp.json()
        text = data.get("extract", "") or ""

    # Если текста достаточно — этого хватит
    if len(text) >= 220:
        return text.strip()

    # --- 2) Если слишком коротко — берём intro целиком ---
    params = {
        "action": "query",
        "prop": "extracts",
        "exintro": True,          # только вводная часть
        "explaintext": True,      # без html
        "exsectionformat": "plain",
        "titles": decoded,
        "format": "json"
    }

    resp2 = requests.get("https://ru.wikipedia.org/w/api.php", params=params, headers=headers)

    if resp2.status_code == 200:
        pages = resp2.json().get("query", {}).get("pages", {})
        for page in pages.values():
            extract = page.get("extract", "")
            if extract and len(extract) > len(text):
                return extract.strip()

    return text.strip()

def clean_wikipedia_extract(text):
    if not text:
        return ""
    text = re.sub(r"[́̀̆̋̄̌]", "", text)           # ударения
    text = re.sub(r'\[.*?]', '', text)             # [1], [K 1]
    text = re.sub(r'{{.*?}}', '', text)            # шаблоны
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def extract_year(date_str):
    if not date_str:
        return None
    try:
        return int(date_str[:4])
    except:
        match = re.match(r"(\d{4})", date_str)
        return int(match.group(1)) if match else None

class Command(BaseCommand):
    help = "Импорт книг из Wikidata/Wikipedia на русском языке"

    def handle(self, *args, **options):
        total_saved = 0

        for author_name, author_qid in AUTHOR_MAP.items():
            self.stdout.write(self.style.WARNING(f"\n=== АВТОР: {author_name} ({author_qid}) ==="))

            books_data = get_books_from_wikidata(author_qid)
            self.stdout.write(self.style.NOTICE(f"Получено {len(books_data)} записей из Wikidata"))

            if not books_data:
                continue

            books_dict = {}
            for item in books_data:
                book_uri = item["book"]["value"]
                if book_uri not in books_dict:
                    books_dict[book_uri] = {
                        "title": item.get("bookLabel", {}).get("value"),
                        "wikidata_desc": item.get("description", {}).get("value", ""),
                        "year": extract_year(item.get("pubDate", {}).get("value")),
                        "genres": [],
                        "image": item.get("image", {}).get("value"),
                        "wiki_title": item.get("wikiTitle", {}).get("value"),
                    }
                if "genreLabel" in item:
                    books_dict[book_uri]["genres"].append(item["genreLabel"]["value"])

            for book_info in books_dict.values():
                title = book_info["title"]
                if not title:
                    continue

                title_lower = title.lower()
                skip_keywords = ["сборник", "том", "часть", "издание", "избранное", "перевод", "собрание сочинений"]
                if any(k in title_lower for k in skip_keywords):
                    continue

                # ОПИСАНИЕ
                description = book_info["wikidata_desc"]
                if book_info["wiki_title"]:
                    # self.stdout.write(self.style.NOTICE(f"Есть статья Википедии для {title}: {book_info['wiki_title']}"))
                    extract_description = get_wikipedia_extract(book_info["wiki_title"])
                    if extract_description:
                        description = extract_description
                    #     self.stdout.write(self.style.NOTICE(f"Описание взято из Википедии (длина {len(extract_description)})"))
                    # else:
                    #     self.stdout.write(self.style.WARNING(f"Пустой extract из Википедии для {title}"))

                # АВТОР
                author_name_split = author_name.split()
                shortname = ""
                for i in range(0, len(author_name_split)):
                    if i != len(author_name_split) - 1:
                        shortname += author_name_split[i][0] + '. '
                    else:
                        shortname += author_name_split[i]
                author_obj, _ = Author.objects.get_or_create(
                    fullname=author_name,
                    defaults={"shortname": shortname}
                )

                if Book.objects.filter(title=title, author=author_obj).exists():
                    self.stdout.write(self.style.WARNING(f"Книга уже существует: {title}"))
                    continue

                if book_info["year"] is None:
                    continue

                # ЖАНРЫ
                genre_objects = []
                for cat in set(book_info["genres"]):
                    if not cat:
                        continue
                    slug = slugify(cat, allow_unicode=True)
                    if not slug:
                        slug = "zhanr-bez-sluga"
                    genre, _ = Genre.objects.get_or_create(
                        slug=slug,
                        defaults={"genre": cat.capitalize()}
                    )
                    genre_objects.append(genre)

                if not genre_objects:
                    continue

                # СОЗДАНИЕ КНИГИ
                book = Book.objects.create(
                    title=title,
                    author=author_obj,
                    description=description,
                    release_year=book_info["year"],
                    is_published=True
                )
                book.genres.set(genre_objects)

                # ОБЛОЖКА
                image_url = book_info.get("image")
                if image_url:
                    try:
                        # Правильное извлечение имени файла
                        filename = image_url.split("/Special:FilePath/")[-1]
                        if not filename:
                            raise ValueError("Не удалось извлечь имя файла")

                        # Прямой URL — это и есть image_url из Wikidata! Он редиректит на картинку.
                        img_response = requests.get(image_url, headers={"User-Agent": "BookImporter/1.0"})
                        if img_response.status_code == 200:
                            book.poster.save(
                                f"{book.id}-{slugify(title, allow_unicode=True)}.jpg",
                                ContentFile(img_response.content),
                                save=True
                            )
                            # self.stdout.write(self.style.SUCCESS(f"Обложка скачана для {title}"))
                        else:
                            self.stdout.write(self.style.WARNING(f"Ошибка скачивания обложки {title}: {img_response.status_code}"))
                    except Exception as e:
                        self.stdout.write(self.style.WARNING(f"Ошибка обработки обложки для {title}: {e}"))

                total_saved += 1
                self.stdout.write(self.style.SUCCESS(f"Добавлена книга: {title} ({book_info['year']})"))

                time.sleep(3)  # Пауза между книгами

            time.sleep(5)  # Пауза между авторами

        self.stdout.write(self.style.SUCCESS(f"\nГОТОВО! Добавлено книг: {total_saved}"))