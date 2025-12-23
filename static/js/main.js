document.addEventListener("DOMContentLoaded", function () { // кнопка "Загрузить ещё"
    const btn = document.getElementById("load-more");
    const container = document.getElementById("books-container");

    if (!btn) return;

    btn.addEventListener("click", async function () {
        let nextPage = btn.dataset.next;

        const response = await fetch(`?page=${nextPage}`);
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
