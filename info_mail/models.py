from django.db import models
import random
import string

def generate_hash_value():
    letters = string.ascii_letters
    random_letters = ''.join(random.choice(letters) for _ in range(8))
    return random_letters.lower()


class WeeklyMails(models.Model):
    week = models.IntegerField()
    year = models.IntegerField()

    class Meta:
        unique_together = ('week', 'year')
    reference = models.CharField(max_length=255, blank=True)

    def save(self, *args, **kwargs):
        if not self.reference:
            # Generate hash value
            self.reference = generate_hash_value()
        super().save(*args, **kwargs)
    upload_date = models.DateField()
    html_file = models.FileField(upload_to='html_files/', blank=True)
