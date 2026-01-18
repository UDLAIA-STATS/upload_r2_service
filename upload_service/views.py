
import asyncio
import logging
import re
import uuid
import httpx
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError
from rest_framework import status
from .serializers import VideoUploadSerializer
from .service import upload_with_progress
from .utils import error_response, format_serializer_errors

logger = logging.getLogger(__name__)

class VideoKeyGenerate(APIView):
    """
    Genera una clave única para el video que se usará durante la subida y procesamiento.
    """
    def post(self, request):
        video_name = request.data.get("video_name")
        try:
            if not video_name:
                raise ValidationError({"video_name": "Este campo es obligatorio."})
            key = f"{uuid.uuid4()}_{video_name}"
            if len(key) > 100:
                key  = key[-100:]
            regex = r'^[a-zA-Z0-9_\-\.]+$'
            if not re.match(regex, key):
                key = re.sub(r'[^a-zA-Z0-9_\-\.]', '_', key) 

            return Response({"video_key": key}, status=status.HTTP_200_OK)
        except ValidationError as ve:
            return error_response(
                "Error de validación.",
                ve.detail,
                status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            return error_response(
                "Error al generar la clave del video.",
                str(e),
                status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class CloudflareVideoUpload(APIView):
    """
    Pide a Cloudflare un upload URL directo que el frontend usará para subir el archivo.
    """
    def post(self, request):
        try:
            logger.info("Iniciando subida de video | ip=%s | data_keys=%s", 
                        request.META.get('REMOTE_ADDR'), list(request.data.keys()))

            # 1. Validar archivo con el serializer
            serializer = VideoUploadSerializer(data=request.data)
            if not serializer.is_valid():
                errors = format_serializer_errors(serializer.errors)
                logger.warning("Validación fallida | errors=%s", errors)
                raise ValidationError(errors)

            video_file = request.FILES['video']
            id_partido = request.data.get("id_partido")
            video_key = request.data.get("video_key")

            logger.info("Datos validados | video_key=%s | id_partido=%s | filename=%s",
                        video_key, id_partido, video_file.name)

            # 2. Ejecutar subida con progreso
            asyncio.run(
                upload_with_progress(
                    video_file,
                    video_file.name,
                    id_partido,
                    video_key)
            )

            logger.info("Subida finalizada con éxito | video_key=%s", video_key)

            return Response(
                {
                    "key": video_key,
                    "message": "Video subido correctamente. El análisis comenzará automáticamente."
                },
                status=status.HTTP_201_CREATED
            )

        except httpx.HTTPStatusError as http_err:
            logger.exception("Error HTTP durante la subida | video_key=%s | status_code=%s | response_text=%s",
                             request.data.get("video_key"), http_err.response.status_code, http_err.response.text)
            return error_response(
                "Error HTTP durante la subida del video.",
                str(http_err),
                status.HTTP_502_BAD_GATEWAY
            )

        except ValidationError as ve:
            logger.warning("Error de validación | detail=%s", ve.detail)
            return error_response(
                "Error de validación.",
                ve.detail,
                status.HTTP_400_BAD_REQUEST
            )

        except Exception as e:
            logger.exception("Error inesperado en la subida | video_key=%s | error=%s", request.data.get("video_key"), str(e))
            return error_response(
                "Error inesperado durante la subida del video.",
                str(e),
                status.HTTP_500_INTERNAL_SERVER_ERROR
            )