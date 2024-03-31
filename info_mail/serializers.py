# serializers.py

from rest_framework import serializers
from .models import WeeklyMails


class WeeklyMailsSerializer(serializers.ModelSerializer):
    class Meta:
        model = WeeklyMails
        fields = ["week", "year", "upload_date", "html_file"]

        def update(self, instance, validated_data):
            # Compare the uploaded data with existing entries
            if instance.week == validated_data.get('week') and instance.year == validated_data.get('year'):
                # Update the other entries
                instance.upload_date = validated_data.get('upload_date', instance.upload_date)
                instance.html_file = validated_data.get('html_file', instance.html_file)
                instance.save()
            else:
                # Create a new entry
                instance = self.Meta.model(**validated_data)
                instance.save()

            return instance