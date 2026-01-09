from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type, before_sleep_log
import asyncio
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
    reraise=False
)
async def _trigger_analysis(object_key: str, id_partido: int, video_id: str):
    async with httpx.AsyncClient(timeout=10) as analysis_client:
        res = await analysis_client.post(
            f"{config('ANALISYS_SERVICE_URL')}/analyze/run",
            json={"video_name": object_key, "match_id": id_partido}
        )
        res.raise_for_status()
        logger.info("Análisis iniciado con éxito | video_key=%s | status_code=%s", video_id, res.status_code)

async def _chunked_reader_with_progress(
        file_obj,
        total_size: int,
        video_id: str,
        notify_url: str,
        chunk_size: int = CHUNK_SIZE):
    """Lee el archivo por trozos y notifica progreso."""
    chunks_totales = math.ceil(total_size / chunk_size)
    chunk_num = 0
    bytes_enviados = 0

    while True:
        chunk = file_obj.read(chunk_size)
        if not chunk:
            break

        chunk_num += 1
        bytes_enviados += len(chunk)
        progress = int((chunk_num / chunks_totales) * 100)

        logger.debug("Chunk %s/%s  (%s%%)", chunk_num, chunks_totales, progress)

        # notificación asíncrona (no bloqueante)
        asyncio.create_task(
            httpx.AsyncClient(timeout=10).post(
                notify_url,
                json={"video_id": video_id, "status": "uploading", "progress": progress}
            )
        )
        yield chunk


async def upload_with_progress(file_obj, filename: str, id_partido: int, video_id: str):
    logger.info("Starting upload | video_id=%s | filename=%s | match_id=%s",
                video_id, filename, id_partido)

    notify_url = f"{config('VIDEO_UPLOAD_NOTIFY_URL')}/start-video-upload/"

    # 1) inicio
    async with httpx.AsyncClient(timeout=30) as client:
        await client.post(
            notify_url,
            json={"video_id": video_id, "status": "started", "progress": 0})

    # 2) URL de subida
    worker_url = str(config("WORKER_URL"))
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(worker_url, json={"filename": filename})
        r.raise_for_status()
        data = r.json()
        upload_url = data["uploadUrl"]
        object_key = data["objectKey"]

    # 3) preparar archivo
    file_obj.seek(0)
    total_size = file_obj.size

    # 4) subida con progreso
    async with httpx.AsyncClient(timeout=None) as client:
        resp = await client.put(
            upload_url,
            content=_chunked_reader_with_progress(
                file_obj,
                total_size,
                video_id,
                notify_url),
            headers={"Content-Length": str(total_size)}
        )
        resp.raise_for_status()

    # 5) fin
    async with httpx.AsyncClient() as client:
        await client.post(
            notify_url,
            json={"video_id": video_id, "status": "finished", "progress": 100})

    try:
        await _trigger_analysis(object_key, id_partido, video_id)
    except Exception:
        logger.exception("Falló el análisis después de 3 intentos | video_key=%s", video_id)

    return {"message": "Video subido correctamente. El análisis se iniciará en breve."}