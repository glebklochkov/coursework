from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.views import LoginView
from django.shortcuts import render
from django.urls import reverse_lazy
from django.views.generic import CreateView

from users.forms import UserRegistrationForm


class UserLoginView(LoginView):
    form_class = AuthenticationForm
    template_name = 'registration/login.html'


class UserRegistrationView(CreateView):
    form_class = UserRegistrationForm
    template_name = 'registration/registration.html'
    success_url = reverse_lazy('login')
