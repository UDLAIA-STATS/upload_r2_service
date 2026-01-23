import logging
import re
import uuid
import httpx
from rest_framework.views import APIView
from rest_framework.response import Response
from asgiref.sync import async_to_sync
from rest_framework.exceptions import ValidationError
from rest_framework import status
import tenacity
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
            regex = r'^[a-zA-Z0-9_\-\.]+$'
            id = uuid.uuid4()
            video_name = re.sub(r'[^a-zA-Z0-9_\-\.]', '_', video_name)
            key = ""
            if id and len(video_name) > 50:
                key = f"{id}_{video_name[:50]}"
            else:
                key = f"{id}_{video_name}"
            
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
            color = request.data.get("color")

            logger.info("Datos validados | video_key=%s | id_partido=%s | filename=%s",
                        video_key, id_partido, video_file.name)

            async_to_sync(upload_with_progress)(
                video_file,
                video_file.name,
                id_partido,
                video_key,
                color
            )

            logger.info("Subida finalizada con éxito | video_key=%s", video_key)

            return Response(
                {
                    "key": video_key,
                    "message": "Video subido correctamente. El análisis comenzará automáticamente."
                },
                status=status.HTTP_201_CREATED
            )
        
        except httpx.TimeoutException as timeout_err:
            logger.exception("Timeout durante la subida | video_key=%s | error=%s",
                             request.data.get("video_key"), str(timeout_err))
            return error_response(
                "El tiempo de subida ha caducado. Intente de nuevo más tarde.",
                str(timeout_err),
                status.HTTP_504_GATEWAY_TIMEOUT
            )
        
        except tenacity.RetryError as retry_err:
            logger.exception("Error al iniciar el análisis tras la subida | video_key=%s | error=%s",
                             request.data.get("video_key"), str(retry_err))
            return error_response(
                "Error al iniciar el análisis tras la subida del video.",
                str(retry_err),
                status.HTTP_500_INTERNAL_SERVER_ERROR
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