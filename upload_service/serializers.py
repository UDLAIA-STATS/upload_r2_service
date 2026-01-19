from rest_framework import serializers

class VideoUploadSerializer(serializers.Serializer):
    video = serializers.FileField(required=True)
    video_key = serializers.CharField(required=True, max_length=255)
    id_partido = serializers.IntegerField(required=True)

    def validate_video_key(self, value):
        if not value:
            raise serializers.ValidationError("El campo video_key es obligatorio.")
        return value

    def validate_video(self, file):
        allowed_extensions = ["mp4", "mov", "mkv", "avi"]
        max_file_size_gb = 5 # GB
        max_bytes = max_file_size_gb * 1024 * 1024 * 1024 # 5 GB

        ext = file.name.split(".")[-1].lower()
        if ext not in allowed_extensions:
            raise serializers.ValidationError(
                f"Formato no permitido. Extensiones válidas: {', '.join(allowed_extensions)}"
            )

        if file.size > max_bytes:
            raise serializers.ValidationError(
                f"El archivo supera los {max_file_size_gb} GB permitidos."
            )

        if not file.content_type.startswith("video"):
            raise serializers.ValidationError(
                "El archivo subido no parece ser un video válido."
            )

        return file
    
    def validate_id_partido(self, value):
        if value <= 0:
            raise serializers.ValidationError("El id_partido debe ser mayor a 0.")
        return value
