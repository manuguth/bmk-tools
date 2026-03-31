from django import forms
from django_summernote.widgets import SummernoteWidget

from .models import WeeklyMails


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