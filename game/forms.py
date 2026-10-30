from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm

User = get_user_model()


class RegisterForm(UserCreationForm):
    """Регистрация: имя игрока (логин), необязательная почта и пароль."""

    email = forms.EmailField(label="Эл. почта (необязательно)", required=False)

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "email")
        labels = {"username": "Имя игрока"}
