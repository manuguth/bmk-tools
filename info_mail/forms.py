from django import forms
from django_summernote.widgets import SummernoteWidget

from .models import NewsletterSettings, WeeklyMails


class NewsletterSettingsForm(forms.ModelForm):
    class Meta:
        model = NewsletterSettings
        fields = [
            "recipient",
            "from_email",
            "km_appointments_url",
            "km_requests_url",
            "default_test_email",
        ]
        widgets = {
            "recipient": forms.EmailInput(attrs={"class": "form-control", "placeholder": "hauptkapelle@bmk-buggingen.de"}),
            "from_email": forms.EmailInput(attrs={"class": "form-control", "placeholder": "news@bmk-buggingen.de"}),
            "km_appointments_url": forms.URLInput(attrs={"class": "form-control", "placeholder": "https://app.konzertmeister.de/api/..."}),
            "km_requests_url": forms.URLInput(attrs={"class": "form-control", "placeholder": "https://app.konzertmeister.de/api/..."}),
            "default_test_email": forms.EmailInput(attrs={"class": "form-control", "placeholder": "deine@email.de"}),
        }


class UploadFileForm(forms.Form):
    file = forms.FileField()


SUMMERNOTE_ATTRS = {
    "summernote": {
        "width": "100%",
        "height": "300",
        "toolbar": [
            ["style", ["style"]],
            ["font", ["bold", "italic", "underline", "clear"]],
            ["color", ["color"]],
            ["para", ["ul", "ol", "paragraph"]],
            ["table", ["table"]],
            ["insert", ["link", "picture"]],
            ["view", ["fullscreen", "codeview", "help"]],
        ],
    }
}


class NewsletterComposeForm(forms.ModelForm):
    class Meta:
        model = WeeklyMails
        fields = ["intro", "info_content", "events", "konzert", "sonstiges"]
        widgets = {
            "intro": SummernoteWidget(attrs=SUMMERNOTE_ATTRS),
            "info_content": SummernoteWidget(attrs=SUMMERNOTE_ATTRS),
            "events": SummernoteWidget(attrs=SUMMERNOTE_ATTRS),
            "konzert": SummernoteWidget(attrs=SUMMERNOTE_ATTRS),
            "sonstiges": SummernoteWidget(attrs=SUMMERNOTE_ATTRS),
        }