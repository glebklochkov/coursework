// Кнопка "Загрузить ещё"
document.addEventListener("DOMContentLoaded", function () {
    const btn = document.getElementById("load-more");
    const container = document.getElementById("books-container");

    if (!btn) return;

    btn.addEventListener("click", async function () {
        let nextPage = btn.dataset.next;

        // Берём текущий URL и меняем/добавляем только page
        const url = new URL(window.location.href);
        url.searchParams.set('page', nextPage);

        const response = await fetch(url.toString());
        const html = await response.text();

        // создаём временный DOM
        const doc = new DOMParser().parseFromString(html, "text/html");

        // вытаскиваем новые карточки
        const newItems = doc.querySelectorAll("#books-container .col-md-6");

        newItems.forEach(el => container.appendChild(el));

        // обновляем кнопку
        const newButton = doc.querySelector("#load-more");

        if (newButton) {
            btn.dataset.next = newButton.dataset.next;
        } else {
            btn.remove();
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




