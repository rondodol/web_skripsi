from django import forms
from django.contrib.auth.models import User
import re

class LoginForm(forms.Form):
    username = forms.CharField(
        max_length=150,
        widget=forms.TextInput(attrs={'placeholder': 'Username', 'class': 'form-control'})
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'placeholder': 'Password', 'class': 'form-control'})
    )

class RecommendForm(forms.Form):
    game_name = forms.CharField(label="Nama Game (opsional)", required=False)
    genre = forms.CharField(label="Genre (opsional)", required=False)
    platform = forms.CharField(label="Platform (opsional)", required=False)

class RegisterForm(forms.Form):
    username = forms.CharField(
        max_length=150,
        widget=forms.TextInput(attrs={'placeholder': 'Username', 'class': 'form-control'}),
        label="Username"
    )
    password1 = forms.CharField(
        widget=forms.PasswordInput(attrs={'placeholder': 'Password', 'class': 'form-control'}),
        label="Password"
    )
    password2 = forms.CharField(
        widget=forms.PasswordInput(attrs={'placeholder': 'Konfirmasi Password', 'class': 'form-control'}),
        label="Konfirmasi Password"
    )

    def clean_username(self):
        uname = self.cleaned_data.get('username')
        if User.objects.filter(username=uname).exists():
            raise forms.ValidationError("Username sudah terdaftar.")
        return uname

    def clean_password1(self):
        pw = self.cleaned_data.get('password1')
        if len(pw) < 8:
            raise forms.ValidationError("Password minimal 8 karakter.")
        if not re.search(r'[A-Za-z]', pw) or not re.search(r'[0-9]', pw):
            raise forms.ValidationError("Password harus mengandung huruf dan angka.")
        return pw

    def clean(self):
        cleaned = super().clean()
        p1 = cleaned.get('password1')
        p2 = cleaned.get('password2')
        if p1 and p2 and p1 != p2:
            raise forms.ValidationError("Password dan Konfirmasi Password tidak cocok.")
        return cleaned

class RatingForm(forms.Form):
    RATING_CHOICES = [(i, str(i)) for i in range(1, 6)]
    rating = forms.ChoiceField(choices=RATING_CHOICES, widget=forms.RadioSelect)