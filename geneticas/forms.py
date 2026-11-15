"""Selección entera de estrellas; identidad y genética se determinan en la vista."""
from django import forms


class ValoracionForm(forms.Form):
    puntuacion = forms.TypedChoiceField(
        label="Puntuación",
        choices=[(numero, f"{numero} estrella{'s' if numero != 1 else ''}") for numero in range(1, 6)],
        coerce=int,
        widget=forms.RadioSelect,
        error_messages={
            "required": "Selecciona una puntuación de 1 a 5 estrellas.",
            "invalid_choice": "La puntuación debe ser un entero entre 1 y 5.",
        },
    )
