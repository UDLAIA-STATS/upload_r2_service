from django.db import models

class Video(models.Model):
    title = models.CharField(max_length=255, blank=True)
    description = models.TextField(blank=True)
    stream_id = models.CharField(max_length=255, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title or self.stream_id

