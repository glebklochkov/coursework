// Кнопка "Загрузить ещё"
document.addEventListener("DOMContentLoaded", function () {
    const btn = document.getElementById("load-more");
    const container = document.getElementById("books-container");

    if (!btn) return;

    btn.addEventListener("click", async function () {
        let nextPage = btn.dataset.next;

        // Берём текущий URL и меняем/добавляем только параметр page
        const url = new URL(window.location.href);
        url.searchParams.set('page', nextPage);

        try {
            const response = await fetch(url.toString());
            const html = await response.text();

            // Создаём временный DOM для парсинга
            const doc = new DOMParser().parseFromString(html, "text/html");

            // ИСПРАВЛЕНО: берем всех прямых потомков-дивов из контейнера
            // Это сработает для любых классов сетки (col-6, col-md-4 и т.д.)
            const newItems = doc.querySelectorAll("#books-container > div");

            if (newItems.length > 0) {
                newItems.forEach(el => container.appendChild(el));
            }

            // Обновляем состояние кнопки
            const newButton = doc.querySelector("#load-more");

            if (newButton) {
                btn.dataset.next = newButton.dataset.next;
            } else {
                // Если следующей страницы нет — удаляем кнопку
                btn.remove();
            }
        } catch (error) {
            console.error("Ошибка при подгрузке книг:", error);
        }
    });
});

// Кнопки "прочитано" и "в закладки"
document.addEventListener('DOMContentLoaded', () => {

    document.querySelectorAll('.js-toggle').forEach(button => {
        button.addEventListener('click', async () => {

            const url = button.dataset.url;

            const response = await fetch(url, {
                method: "POST",
                headers: {
                    "X-CSRFToken": getCookie("csrftoken"),
                }
            });

            const data = await response.json();

            if (data.status) {
                button.classList.toggle('active');
            }

            const icon = button.querySelector('i');

            if (icon.classList.contains('bi-bookmark') || icon.classList.contains('bi-bookmark-fill')) {
                icon.className = button.classList.contains('active')
                    ? 'bi bi-bookmark-fill'
                    : 'bi bi-bookmark';
            }

            if (icon.classList.contains('bi-eye') || icon.classList.contains('bi-eye-fill')) {
                icon.className = button.classList.contains('active')
                    ? 'bi bi-eye-fill'
                    : 'bi bi-eye';
            }
        });
    });
});


function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let cookie of cookies) {
            cookie = cookie.trim();
            if (cookie.startsWith(name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

// кнопки оценки
document.addEventListener('DOMContentLoaded', () => {

    document.querySelectorAll('.rating-star').forEach(star => {
        star.addEventListener('click', function () {

            const value = parseInt(this.dataset.value);
            const container = this.closest('.rating');
            const bookId = container.dataset.bookId;
            const currentRating = parseInt(container.dataset.userRating || 0);

            // если нажали на ту же оценку — снимаем её
            const newValue = (value === currentRating) ? 0 : value;

            fetch('/rate/', {
                method: 'POST',
                headers: {
                    'X-CSRFToken': getCookie('csrftoken'),
                    'Content-Type': 'application/x-www-form-urlencoded',
                },
                body: `book_id=${bookId}&value=${newValue}`
            })
            .then(res => res.json())
            .then(data => {
                if (data.success) {

                    container.dataset.userRating = newValue;

                    if (newValue === 0) {
                        highlightStars(container, 0);
                        document.getElementById('user-rating').textContent = '—';
                    } else {
                        highlightStars(container, newValue);
                        document.getElementById('user-rating').textContent = newValue;
                    }
                }
            });
        });
    });

});


function highlightStars(container, value) {
    container.querySelectorAll('.rating-star').forEach(star => {
        if (parseInt(star.dataset.value) <= value) {
            star.classList.remove('bi-star');
            star.classList.add('bi-star-fill');
        } else {
            star.classList.remove('bi-star-fill');
            star.classList.add('bi-star');
        }
    });
}

document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('.rating').forEach(container => {
        const userRating = parseInt(container.dataset.userRating || 0);
        if (userRating > 0) {
            highlightStars(container, userRating);
        }
    });
});

// фильтры
// Универсальный поиск внутри множественных списков
document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('.filter-search-input').forEach(input => {
        input.addEventListener('input', function () {
            const filterValue = this.value.toLowerCase().trim();
            const targetId = this.dataset.target;
            const container = document.getElementById(targetId);

            if (!container) return;

            const labels = container.querySelectorAll('label');

            labels.forEach(label => {
                const text = label.textContent.toLowerCase();
                label.style.display = text.includes(filterValue) ? '' : 'none';
            });
        });

        // Очистка при фокусе (опционально)
        input.addEventListener('focus', function () {
            if (this.value === '') {
                // можно сбросить видимость всех, но обычно не нужно
            }
        });
    });
});


function handleImageError(image) {
    // 1. Скрываем само битое изображение
    image.style.display = 'none';

    // 2. Ищем ближайший контейнер (это может быть ссылка или div)
    const container = image.parentElement;

    // 3. Находим внутри этого контейнера заглушку
    const fallback = container.querySelector('.fallback-poster');

    if (fallback) {
        fallback.classList.remove('d-none');
        // Дополнительно: если у контейнера есть специфические стили для пустого состояния
        fallback.style.display = 'flex';
    }
}



