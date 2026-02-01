from django.db.models import Avg, Count, Q, F
from books.models import Genre, Author, Book


def genre_preferences(user):
    return {
        g.id: g.avg_rating
        for g in (
            Genre.objects
            .filter(books__ratings__user=user)
            .annotate(
                avg_rating=Avg(F('books__ratings__value') - 3),
                cnt=Count('books__ratings'),
            )
        )
    }


def author_preferences(user):
    return {
        a.id: a.avg_rating
        for a in (
            Author.objects
            .filter(book__ratings__user=user)
            .annotate(
                avg_rating=Avg(F('book__ratings__value') - 3),
                cnt=Count('book__ratings'),
            )
        )
    }


def candidate_books(user, genre_prefs, author_prefs):
    return (
        Book.objects
        .filter(
            Q(genres__id__in=genre_prefs.keys()) |
            Q(author__id__in=author_prefs.keys())
        )
        .exclude(Q(ratings__user=user) | Q(users_read=user))
        .distinct()
        .prefetch_related('genres', 'author')
    )


def book_score(book, genre_prefs, author_prefs):
    score = 0

    if book.author_id in author_prefs:
        score += author_prefs[book.author_id]

    for genre in book.genres.all():
        if genre.id in genre_prefs:
            score += genre_prefs[genre.id]

    return score


def recommend_books(user, min_score=1.1):
    genre_prefs = genre_preferences(user)
    author_prefs = author_preferences(user)

    if not genre_prefs and not author_prefs:
        return Book.objects.none()

    books = candidate_books(user, genre_prefs, author_prefs)

    # scored = []
    # for book in books:
    #     score = book_score(book, genre_prefs, author_prefs)
    #     if score >= min_score:
    #         scored.append((book, score))
    #
    # scored.sort(key=lambda x: x[1], reverse=True)
    #
    # return [book for book, score in scored]
    result = []
    for book in books:
        score = book_score(book, genre_prefs, author_prefs)
        if score >= min_score:
            book.recommend_score = score
            result.append(book)

    return result
