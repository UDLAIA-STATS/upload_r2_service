from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log)
import logging
import httpx
from decouple import config

from upload_service.utils.file_management import (
    save_uploaded_file_temporarily,
    chunked_reader_with_progress,
    cleanup_temp_file)
from upload_service.utils.timeout import calculate_upload_timeout

logger = logging.getLogger(__name__)


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=2, min=2, max=10),
    retry=retry_if_exception_type((httpx.TimeoutException, httpx.HTTPStatusError)),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True
)
async def _trigger_analysis(object_key: str, id_partido: int, video_id: str):
    async with httpx.AsyncClient(timeout=10) as analysis_client:
        res = await analysis_client.post(
            f"{config('ANALYSIS_SERVICE_URL')}/analyze/run",
            json={"video_name": object_key, "match_id": id_partido}
        )
        res.raise_for_status()
        logger.info("Análisis iniciado con éxito | video_key=%s | status_code=%s", video_id, res.status_code)

async def upload_with_progress(file_obj, filename: str, id_partido: int, video_id: str):
    """Proceso principal de upload con mejor organización."""
    logger.info("Starting upload | video_id=%s | filename=%s | match_id=%s",
                video_id, filename, id_partido)

    # PASO 1: Crear archivo temporal al inicio
    tmp_file_path = None
    try:
        tmp_file_path = await save_uploaded_file_temporarily(file_obj, filename)
        total_size = tmp_file_path.stat().st_size
        
        if not isinstance(total_size, int) or total_size <= 0:
            raise ValueError(f"Tamaño de archivo inválido: {total_size}")
            
        logger.info("Archivo temporal creado | path=%s | size=%s bytes", tmp_file_path, total_size)
        
    except Exception as exc:
        logger.exception("Error al crear archivo temporal | video_id=%s", video_id)
        if tmp_file_path:
            await cleanup_temp_file(tmp_file_path)
        return {"error": f"Error al preparar archivo: {str(exc)}"}

    # PASO 2: Proceso de upload con el archivo temporal listo
    notify_url = f"{config('VIDEO_UPLOAD_NOTIFY_URL')}/start-video-upload/"
    upload_url = None
    object_key = None
    
    try:
        async with httpx.AsyncClient(timeout=30) as notify_client:
            # Notificar inicio
            try:
                await notify_client.post(
                    notify_url,
                    json={"video_id": video_id, "status": "started", "progress": 0}
                )
            except (httpx.HTTPError, httpx.TimeoutException) as exc:
                logger.warning(
                    "Error al notificar inicio | video_id=%s | error=%s",
                    video_id,
                    str(exc),
                )

            # Obtener URL de upload
            worker_url = str(config("WORKER_URL"))
            async with httpx.AsyncClient(timeout=30) as worker_client:
                r = await worker_client.post(worker_url, json={"filename": filename})
                r.raise_for_status()
                data = r.json()
                upload_url = data["uploadUrl"]
                object_key = data["objectKey"]

            # Calcular timeout y realizar upload
            upload_timeout = calculate_upload_timeout(total_size)
            
            async with httpx.AsyncClient(timeout=upload_timeout) as upload_client:
                resp = await upload_client.put(
                    upload_url,
                    content=chunked_reader_with_progress(
                        str(tmp_file_path),
                        total_size,
                        video_id,
                        notify_url,
                        notify_client
                    ),
                    headers={"Content-Length": str(total_size)}
                )
                resp.raise_for_status()

            # Notificar finalización
            await notify_client.post(
                notify_url,
                json={"video_id": video_id, "status": "finished", "progress": 100}
            )

        # PASO 3: Trigger análisis después del upload exitoso
        try:
            await _trigger_analysis(object_key, id_partido, video_id)
        except Exception:
            logger.exception("Error al iniciar análisis | video_key=%s", video_id)
            # No fallamos el upload si el análisis falla

        logger.info("Upload completado exitosamente | video_id=%s", video_id)
        return {"message": "Video subido correctamente. El análisis se iniciará en breve."}

    except Exception as exc:
        logger.exception("Error durante upload | video_id=%s", video_id)
        return {"error": f"Error durante upload: {str(exc)}"}
        
    finally:
        # PASO 4: Siempre limpiar el archivo temporal
        if tmp_file_path:
            await cleanup_temp_file(tmp_file_path)
