from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm

from django import forms


class UserRegistrationForm(UserCreationForm):
    class Meta:
        model = get_user_model()
        fields = ('username', 'email', 'password1', 'password2')


class AccountSettingsForm(forms.ModelForm):
    class Meta:
        model = get_user_model()
        fields = ('username', 'email', 'avatar')
        widgets = {
            'username': forms.TextInput(attrs={
                'class': 'form-control book-title-input'
            }),
            'email': forms.TextInput(attrs={
                'class': 'form-control email-input'
            })
        }



