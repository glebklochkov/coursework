from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.views import LoginView
from django.shortcuts import render
from django.urls import reverse_lazy
from django.urls.base import reverse
from django.views.generic import CreateView, DetailView, UpdateView

from users.forms import UserRegistrationForm, AccountSettingsForm
from users.models import User


class UserAccountView(DetailView):
    model = User
    template_name = 'users/profile.html'
    context_object_name = 'user'


class AccountSettingsView(UpdateView):
    model = User
    form_class = AccountSettingsForm
    context_object_name = 'user'
    template_name = 'users/profile_settings.html'

    def get_success_url(self):
        user_id = self.request.user.id
        return reverse_lazy('users:profile', kwargs={'pk': user_id})


class UserLoginView(LoginView):
    form_class = AuthenticationForm
    template_name = 'registration/login.html'

    def get_success_url(self):
        user_id = self.request.user.id
        return reverse_lazy('users:profile', kwargs={'pk': user_id})


class UserRegistrationView(CreateView):
    form_class = UserRegistrationForm
    template_name = 'registration/registration.html'
    success_url = reverse_lazy('login')
