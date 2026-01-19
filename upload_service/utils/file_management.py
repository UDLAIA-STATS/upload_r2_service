import logging
from pathlib import Path
import math
import httpx
import aiofiles

CHUNK_SIZE = 5 * 1024 * 1024  # 5 MB
logger = logging.getLogger(__name__)

async def chunked_reader_with_progress(
        file_path: str,
        total_size: int,
        video_id: str,
        notify_url: str,
        progress_client: httpx.AsyncClient,
        chunk_size: int = CHUNK_SIZE):
    """Lee el archivo por trozos de forma asíncrona y notifica progreso."""
    chunks_totales = math.ceil(total_size / chunk_size)
    chunk_num = 0

    async with aiofiles.open(file_path, 'rb') as file:
        while True:
            chunk = await file.read(chunk_size)
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

async def save_uploaded_file_temporarily(file_obj, filename: str) -> Path:
    """Guarda el archivo subido temporalmente y retorna la ruta."""
    # Crear directorio temp si no existe
    temp_dir = Path("tmp")
    temp_dir.mkdir(exist_ok=True)
    
    tmp_file_path = temp_dir / f"{filename}_{id(file_obj)}.tmp"
    
    with open(tmp_file_path, 'wb') as tmp_file:
        for chunk in file_obj.chunks():
            tmp_file.write(chunk)
    
    return tmp_file_path

async def cleanup_temp_file(file_path: Path):
    """Limpia el archivo temporal de forma segura."""
    try:
        if file_path.exists():
            file_path.unlink()
            logger.debug("Archivo temporal eliminado: %s", file_path)
    except OSError as exc:
        logger.warning("No se pudo eliminar el archivo temporal %s: %s", file_path, exc)
