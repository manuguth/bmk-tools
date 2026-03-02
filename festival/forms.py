from django import forms
from .models import Participant


class ParticipantSignUpForm(forms.ModelForm):
    class Meta:
        model = Participant
        fields = ["name"]
        widgets = {
            "name": forms.TextInput(
                attrs={
                    "class": "form-control form-control-lg",
                    "placeholder": "Your name",
                    "required": True,
                }
            ),
        }
        labels = {
            "name": "Your Name",
        }
