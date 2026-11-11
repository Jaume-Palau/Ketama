"""Formularios basados en la autenticación nativa de Django."""
from django import forms
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm

from .models import Socio


class AccesoSocioForm(AuthenticationForm):
    username = forms.CharField(
        label="Número de socio",
        max_length=150,
        widget=forms.TextInput(attrs={"autofocus": True, "autocomplete": "username"}),
    )

    def confirm_login_allowed(self, user):
        super().confirm_login_allowed(user)
        if user.is_staff or user.is_superuser or not Socio.objects.filter(
            usuario=user
        ).exists():
            # El mismo mensaje que para unas credenciales incorrectas.
            raise self.get_invalid_login_error()


class CambioPasswordSocioForm(PasswordChangeForm):
    def clean_new_password1(self):
        password = self.cleaned_data["new_password1"]
        if self.user.check_password(password):
            raise forms.ValidationError(
                "La nueva contraseña debe ser distinta de la actual."
            )
        return password
