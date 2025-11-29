from django.db import models
import uuid


class Video(models.Model):
    file_key = models.CharField(max_length=500, unique=True)

    file_url = models.URLField(max_length=1000, blank=True)

    original_filename = models.CharField(max_length=255, blank=True)

    mime_type = models.CharField(max_length=100, blank=True)
    file_size = models.BigIntegerField(null=True, blank=True)  # en bytes
    extension = models.CharField(max_length=20, blank=True)

    duration_seconds = models.FloatField(null=True, blank=True)
    width = models.IntegerField(null=True, blank=True)
    height = models.IntegerField(null=True, blank=True)
    bitrate = models.BigIntegerField(null=True, blank=True)

    title = models.CharField(max_length=255, blank=True)
    description = models.TextField(blank=True)

    video_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)

    STATUS_CHOICES = (
        ("uploaded", "Uploaded"),
        ("processing", "Processing"),
        ("ready", "Ready"),
        ("failed", "Failed"),
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="uploaded")

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title or self.original_filename or self.file_key
