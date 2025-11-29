from rest_framework import serializers
from upload_service.models import Video

class VideoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Video
        fields = ["id", "title", "description", "stream_id", "created_at"]
        read_only_fields = ["id", "created_at"]
