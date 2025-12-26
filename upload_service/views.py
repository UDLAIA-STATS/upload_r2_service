
import uuid
import requests
from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .serializers import VideoUploadSerializer
from .models import Video
from .service import get_metadata, upload
from asgiref.sync import async_to_sync
from decouple import config

class CloudflareStreamDirectUpload(APIView):
    """
    Pide a Cloudflare un upload URL directo que el frontend usará para subir el archivo.
    """
    def post(self, request):
       # 1. Validar archivo con el serializer
        serializer = VideoUploadSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {"errors": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST
            )

        video_file = request.FILES['video']
        partido = request.data.get("partido", "")
        original_name = video_file.name
        extension = original_name.split(".")[-1].lower()

        file_key = f"{uuid.uuid4()}_{original_name}"
        file_bytes = video_file.read()

        upload(key=file_key, file_bytes=file_bytes)

        file_url = f"{config('PUBLIC_URL')}/{file_key}"

        return Response(
            {"key": file_key},
            status=status.HTTP_201_CREATED
        )

class UploadProgressView(APIView):
    def get(self, request, key: str):
        total_size = request.query_params.get("total")
        if not total_size or not key:
            return Response(
                {"error": "Faltan parámetros obligatorios 'total' o 'key'."},
                status=status.HTTP_400_BAD_REQUEST
            )
        try:
            metadata = get_metadata(key)
            uploaded_size = metadata['ContentLength']
            percentage = round((int(uploaded_size) / int(total_size)) * 100, 2)
            return Response({
                "total": total_size,
                "uploaded": uploaded_size,
                "progress": percentage
            })
        except Exception as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )