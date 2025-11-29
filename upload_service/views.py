
import requests
from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .serializers import VideoSerializer
from .models import Video
from decouple import config

class CloudflareStreamDirectUpload(APIView):
    """
    Pide a Cloudflare un upload URL directo que el frontend usará para subir el archivo.
    """
    def post(self, request):
        """
        Devuelve un objeto con un link de Cloudflare para subir un archivo directamente.
        Si no se configura Cloudflare, devuelve un error 500 con un mensaje de error.
        """
        
        if not config('R2_ACCOUNT_ID') or not config('R2_ACCESS_TOKEN'):
            return Response({"detail": "Cloudflare not configured"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        url = f"https://api.cloudflare.com/client/v4/accounts/{config('R2_ACCOUNT_ID')}/stream/direct_upload"
        payload = {
            "maxDurationSeconds": 60 * 60 * 5  # 5 horas
        }
        headers = {
            "Authorization": f"Bearer {config('R2_ACCESS_TOKEN')}",
            "Content-Type": "application/json"
        }
        r = requests.post(url, json=payload, headers=headers)
        try:
            data = r.json()
        except ValueError:
            return Response({"detail": "Invalid response from Cloudflare"}, status=status.HTTP_502_BAD_GATEWAY)
        return Response(data, status=r.status_code)

class RegisterStreamResult(APIView):
    """
    Recibe del frontend el stream_id (uid) tras finalizar la subida
    y lo guarda en la DB con título/descripcion opcional.
    """
    def post(self, request):
        """
        Recibe del frontend el stream_id (uid) tras finalizar la subida
        y lo guarda en la DB con título/descripcion opcional.
        Si el stream_id ya existe en la DB, devuelve un error 400 con un mensaje de error.
        Returns:
            Response: Un objeto con el video recién guardado en la DB.
        """
        
        serializer = VideoSerializer(data=request.data)
        if serializer.is_valid():
            stream_id = request.data.get("stream_id")
            if Video.objects.filter(stream_id=stream_id).exists():
                return Response({"detail": "Stream ya registrado"}, status=status.HTTP_400_BAD_REQUEST)
            video = serializer.save()
            return Response(VideoSerializer(video).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)