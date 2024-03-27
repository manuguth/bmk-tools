from django.db import models
import hashlib
import time

def generate_hash_value():
    return hashlib.md5(str(time.time()).encode()).hexdigest()

class WeeklyMails(models.Model):
    week = models.IntegerField()
    year = models.IntegerField()
    reference = models.CharField(max_length=255, blank=True)

    def save(self, *args, **kwargs):
        if not self.reference:
            # Generate hash value
            self.reference = generate_hash_value()
        super().save(*args, **kwargs)
    upload_date = models.DateField()
    html_file = models.FileField(upload_to='html_files/', blank=True)
