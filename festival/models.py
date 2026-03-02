import uuid
from django.db import models
from django.utils.text import slugify


class Festival(models.Model):
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("active", "Active"),
        ("completed", "Completed"),
    ]

    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    slug = models.SlugField(unique=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class Shift(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    festival = models.ForeignKey(Festival, on_delete=models.CASCADE, related_name="shifts")
    name = models.CharField(max_length=255)
    start_time = models.TimeField()
    end_time = models.TimeField()
    date = models.DateField()
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} - {self.date}"

    class Meta:
        ordering = ["date", "start_time"]


class Task(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    shift = models.ForeignKey(Shift, on_delete=models.CASCADE, related_name="tasks")
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    required_helpers = models.IntegerField(default=1)
    special_requirements = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.shift.name})"

    @property
    def current_helpers(self):
        return self.participants.count()

    @property
    def is_full(self):
        return self.current_helpers >= self.required_helpers


class Participant(models.Model):
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name="participants")
    name = models.CharField(max_length=255)
    signed_up_at = models.DateTimeField(auto_now_add=True)
    attended = models.BooleanField(default=False)
    notes = models.TextField(blank=True)

    def __str__(self):
        return f"{self.name} - {self.task.name}"

    class Meta:
        ordering = ["signed_up_at"]

