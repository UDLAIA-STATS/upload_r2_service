from __future__ import annotations

import logging
from pathlib import Path
import httpx
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)
from decouple import config

from upload_service.utils.file_management import (
    create_tmp_file,
    chunked_reader_with_progress,
    cleanup_temp_file,
)
from upload_service.utils.responses import error_response, success_response
from upload_service.utils.timeout import calculate_upload_timeout

logger = logging.getLogger(__name__)

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=2, min=2, max=10),
    retry=retry_if_exception_type((httpx.TimeoutException, httpx.HTTPStatusError)),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)
async def _trigger_analysis(object_key: str, id_partido: int, video_id: str) -> None:
    """Lanza el análisis una vez finalizada la subida."""
    async with httpx.AsyncClient(timeout=10) as client:
        res = await client.post(
            f"{config('ANALYSIS_SERVICE_URL')}/analyze/run",
            json={"video_name": object_key, "match_id": id_partido},
        )
        res.raise_for_status()
    logger.info("Analysis triggered", extra={"video_id": video_id, "status_code": res.status_code})

async def _request_upload_urls(filename: str, video_id: str) -> tuple[str, str]:
    """Obtiene URL firmada y object-key del worker."""
    worker_url = str(config("WORKER_URL"))
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(worker_url, json={"filename": filename})
        r.raise_for_status()
    data = r.json()
    return data["uploadUrl"], data["objectKey"]


async def _stream_file_to_storage(
    tmp_path: Path,
    upload_url: str,
    total_size: int,
    video_id: str,
    notify_url: str,
) -> None:
    """Sube el fichero en chunks con notificaciones de progreso."""
    timeout = calculate_upload_timeout(total_size)
    async with httpx.AsyncClient(timeout=timeout) as upload_client:
        await upload_client.put(
            upload_url,
            content=chunked_reader_with_progress(
                str(tmp_path),
                total_size,
                video_id,
                notify_url,
                upload_client,
            ),
            headers={"Content-Length": str(total_size)},
        )


async def _notify_status(
    video_id: str,
    status: str,
    progress: int,
    notify_url: str,
) -> None:
    """Notifica estado al servicio externo (con tolerancia a fallos)."""
    async with httpx.AsyncClient(timeout=30) as client:
        try:
            await client.post(
                notify_url,
                json={"video_id": video_id, "status": status, "progress": progress},
            )
        except httpx.HTTPError as exc:
            logger.warning("Notification failed", extra={"video_id": video_id, "error": str(exc)})


async def _close_pipeline(
    video_id: str,
    id_partido: int,
    object_key: str | None,
    success: bool,
    notify_url: str,
):
    if success and object_key:
        await _notify_status(video_id, "finished", 100, notify_url)
        try:
            await _trigger_analysis(object_key, id_partido, video_id)
        except Exception:
            logger.exception("Analysis launch failed", extra={"video_id": video_id})
        return success_response("La subida del video ha finalizado.", {"video_name": object_key}, 200)

    return error_response(
        "La subida del video ha fallado.",
        {"video_name": object_key},
        500
    )

async def upload_with_progress(
    file_obj,
    filename: str,
    id_partido: int,
    video_id: str,
):
    """Upload pipeline sin anidamiento profundo."""
    logger.info("Upload started", extra={"video_id": video_id, "filename": filename, "match_id": id_partido})

    tmp_path: Path | None = None
    object_key: str | None = None
    notify_url = f"{config('VIDEO_UPLOAD_NOTIFY_URL')}/start-video-upload/"
    success = False

    try:
        try:
            tmp_path = await create_tmp_file(file_obj, filename, video_id)
        except Exception as exc:
            logger.error("Temporary file creation failed after retries", extra={"video_id": video_id})
            raise exc

        total_size = tmp_path.stat().st_size

        await _notify_status(video_id, "started", 0, notify_url)
        upload_url, object_key = await _request_upload_urls(filename, video_id)

        await _stream_file_to_storage(tmp_path, upload_url, total_size, video_id, notify_url)
        success = True

    except Exception:
        logger.exception("Upload pipeline failed", extra={"video_id": video_id})
    finally:
        if tmp_path:
            await cleanup_temp_file(tmp_path)

    return await _close_pipeline(
        video_id=video_id,
        id_partido=id_partido,
        object_key=object_key,
        success=success,
        notify_url=notify_url,
    )
