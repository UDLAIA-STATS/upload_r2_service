from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type, before_sleep_log
import traceback
import logging
import math
import httpx
from decouple import config

logger = logging.getLogger(__name__)
CHUNK_SIZE = 5 * 1024 * 1024  # 5 MB


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

async def _chunked_reader_with_progress(
        file_obj,
        total_size: int,
        video_id: str,
        notify_url: str,
        progress_client: httpx.AsyncClient,
        chunk_size: int = CHUNK_SIZE):
    """Lee el archivo por trozos y notifica progreso."""
    chunks_totales = math.ceil(total_size / chunk_size)
    chunk_num = 0

    while True:
        chunk = file_obj.read(chunk_size)
        if not chunk:
            break

        chunk_num += 1
        progress = int((chunk_num / chunks_totales) * 100)

        logger.debug("Chunk %s/%s  (%s%%)", chunk_num, chunks_totales, progress)

        await progress_client.post(
                notify_url,
                json={"video_id": video_id, "status": "uploading", "progress": progress}
        )
        yield chunk

def calculate_upload_timeout(total_size: int) -> int:
    """Versión para usuarios con internet muy lento (0.5 Mbps)"""
    max_size = 5 * 1024 * 1024 * 1024
    total_size = min(total_size, max_size)

    size_mbits = (total_size * 8) / (1024 * 1024)
    base_seconds = size_mbits / 0.5  # 0.5 Mbps mínimo

    timeout_seconds = int(base_seconds * 1.8)  # 80% margen adicional (180% del tiempo base)

    return max(600, min(14400, timeout_seconds))

async def upload_with_progress(file_obj, filename: str, id_partido: int, video_id: str):
    logger.info("Starting upload | video_id=%s | filename=%s | match_id=%s",
                video_id, filename, id_partido)

    notify_url = f"{config('VIDEO_UPLOAD_NOTIFY_URL')}/start-video-upload/"

    try:
        async with httpx.AsyncClient(timeout=30) as notify_client:
            try:
                await notify_client.post(
                    notify_url,
                    json={"video_id": video_id, "status": "started", "progress": 0})
            except Exception:
                logger.warning(
                    "Error al notificar el inicio de la subida | video_id=%s", video_id)
                traceback.print_exc()

            # 2) URL de subida
            worker_url = str(config("WORKER_URL"))
            async with httpx.AsyncClient(timeout=30) as worker_client:
                r = await worker_client.post(worker_url, json={"filename": filename})
                r.raise_for_status()
                data = r.json()
                upload_url = data["uploadUrl"]
                object_key = data["objectKey"]

            # 3) preparar archivo
            file_obj.seek(0)
            total_size = file_obj.size

            if isinstance(total_size, int):
                upload_timeout = calculate_upload_timeout(total_size)
            else:
                upload_timeout = 1200
            async with httpx.AsyncClient(timeout=upload_timeout) as upload_client:
                resp = await upload_client.put(
                    upload_url,
                    content=_chunked_reader_with_progress(
                        file_obj,
                        total_size,
                        video_id,
                        notify_url,
                        notify_client),
                    headers={"Content-Length": str(total_size)}
                )
                resp.raise_for_status()

            # 5) fin - usar el mismo cliente de notificaciones
            await notify_client.post(
                notify_url,
                json={"video_id": video_id, "status": "finished", "progress": 100})
        try:
            await _trigger_analysis(object_key, id_partido, video_id)
        except Exception:
            logger.exception("Error al iniciar el análisis para el video | video_key=%s", video_id)
        
        return {"message": "Video subido correctamente. El análisis se iniciará en breve."}

    except Exception:
        logger.exception("Falló la subida | video_key=%s", video_id)

