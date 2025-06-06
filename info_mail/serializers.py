# serializers.py

from rest_framework import serializers
from .models import WeeklyMails


class WeeklyMailsSerializer(serializers.ModelSerializer):
    class Meta:
        model = WeeklyMails
        fields = ["week", "year", "upload_date", "html_file"]