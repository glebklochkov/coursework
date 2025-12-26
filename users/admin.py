from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from users.models import User

UserAdmin.fieldsets += (
    (
        'Профиль',
        {
            'fields': (
                'avatar',
            )
        }
    ),
    (
        'Книги',
        {
            'fields': (
                'saved_books',
                'read_books'
            )
        }
    ),
)

admin.site.register(User, UserAdmin)
