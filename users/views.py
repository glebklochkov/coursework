from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.views import LoginView
from django.shortcuts import render
from django.urls import reverse_lazy
from django.views.generic import CreateView, DetailView

from users.forms import UserRegistrationForm
from users.models import User


class UserAccountView(DetailView):
    model = User
    template_name = 'users/profile.html'
    context_object_name = 'user'


class UserLoginView(LoginView):
    form_class = AuthenticationForm
    template_name = 'registration/login.html'


class UserRegistrationView(CreateView):
    form_class = UserRegistrationForm
    template_name = 'registration/registration.html'
    success_url = reverse_lazy('login')
