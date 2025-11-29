from rest_framework import serializers

class VideoUploadSerializer(serializers.Serializer):
    video = serializers.FileField(required=True)
    id_partido = serializers.CharField(required=True, allow_blank=False)

    def validate_video(self, file):
        allowed_extensions = ["mp4", "mov", "mkv", "avi"]
        max_file_size_mb = 5000 # 5GB
        max_bytes = max_file_size_mb * 1024 * 1024 * 1024

        # Validación 1: extensión
        ext = file.name.split(".")[-1].lower()
        if ext not in allowed_extensions:
            raise serializers.ValidationError(
                f"Formato no permitido. Extensiones válidas: {', '.join(allowed_extensions)}"
            )

        # Validación 2: tamaño
        if file.size > max_bytes:
            raise serializers.ValidationError(
                f"El archivo supera los {max_file_size_mb} MB permitidos."
            )

        # Validación 3: tipo MIME
        if not file.content_type.startswith("video"):
            raise serializers.ValidationError(
                "El archivo subido no parece ser un video válido."
            )

        return file
    
    def validate_id_partido(self, value):
        if not value.strip():
            raise serializers.ValidationError("El campo 'id_partido' no puede estar vacío.")
        return value
