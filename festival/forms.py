from django import forms
from .models import Participant, Task, Shift, TaskTemplate


class ParticipantSignUpForm(forms.ModelForm):
    class Meta:
        model = Participant
        fields = ["name", "notes"]
        widgets = {
            "name": forms.TextInput(
                attrs={
                    "class": "form-control form-control-lg",
                    "placeholder": "Your name",
                    "required": True,
                }
            ),
            "notes": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "placeholder": "Optional comment or special requirements",
                    "rows": 3,
                }
            ),
        }
        labels = {
            "name": "Your Name",
            "notes": "Comment (optional)",
        }


# Optional forms for inline editing validation
class InlineTaskForm(forms.ModelForm):
    """Form for inline editing of task details."""
    class Meta:
        model = Task
        fields = ['required_helpers', 'description']
        widgets = {
            'required_helpers': forms.NumberInput(attrs={'min': 1}),
            'description': forms.Textarea(attrs={'rows': 4}),
        }


class InlineShiftForm(forms.ModelForm):
    """Form for inline editing of shift details."""
    class Meta:
        model = Shift
        fields = ['description']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
        }


class InlineParticipantForm(forms.ModelForm):
    """Form for inline editing of participant details."""
    class Meta:
        model = Participant
        fields = ['name', 'attended', 'masked', 'notes']
        widgets = {
            'name': forms.TextInput(),
            'attended': forms.CheckboxInput(),
            'masked': forms.CheckboxInput(),
            'notes': forms.Textarea(attrs={'rows': 3}),
        }


class TaskTemplateForm(forms.ModelForm):
    """Form for task template creation and editing."""
    class Meta:
        model = TaskTemplate
        fields = ['name', 'description', 'required_helpers', 'special_requirements']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Template name',
                'required': True,
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Task description',
            }),
            'required_helpers': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 1,
                'placeholder': 'Number of helpers needed',
            }),
            'special_requirements': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Special requirements',
            }),
        }
