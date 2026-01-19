import logging
from pathlib import Path
import math
import httpx
import aiofiles
import tempfile

from tenacity import before_sleep_log, retry, retry_if_exception_type, stop_after_attempt, wait_fixed

CHUNK_SIZE = 5 * 1024 * 1024  # 5 MB
logger = logging.getLogger(__name__)

async def chunked_reader_with_progress(
        file_path: str,
        total_size: int,
        video_id: str,
        notify_url: str,
        progress_client: httpx.AsyncClient,
        chunk_size: int = CHUNK_SIZE):
    """
    Lee un archivo en chunks y notifica el progreso de la subida

    Se utiliza para subir archivos grandes en chunks y notificar el progreso
    a un servicio externo.

    :param file_path: Path del archivo a leer
    :param total_size: Tamaño total del archivo (en bytes)
    :param video_id: ID del video a subir
    :param notify_url: URL del servicio externo para notificar el progreso
    :param progress_client: Cliente HTTP para notificar el progreso
    :param chunk_size: Tamaño de cada chunk (en bytes). Default: 5MB
    :yield: Un chunk del archivo leido
    """
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

            # Notificación con manejo de errores
            try:
                await progress_client.post(
                    notify_url,
                    json={"video_id": video_id, "status": "uploading", "progress": progress}
                )
            except httpx.HTTPError as e:
                logger.warning("Failed to send progress update: %s", e)
                
            yield chunk

async def save_uploaded_file_temporarily(file_obj, filename: str) -> Path | None:
    # Usar el directorio temporal del sistema (/tmp en contenedores)
    """
    Guarda el archivo subido en un archivo temporal seguro y único en
    el directorio temporal del sistema (/tmp en contenedores).

    El archivo se crea con un nombre único y seguro utilizando
    tempfile.NamedTemporaryFile, y se escribe de forma asíncrona
    utilizando aiofiles.open.

    En caso de error durante la creación, se limpia el archivo
    temporal de forma segura y robusta.

    Returns:
        Path | None: Ruta del archivo temporal creado con éxito, o None
            en caso de error.
    """
    temp_dir = Path(tempfile.gettempdir())
    
    # Crear archivo temporal con nombre único y seguro
    tmp_file = tempfile.NamedTemporaryFile(
        dir=temp_dir,
        prefix=f"upload_{filename}_",
        suffix=".tmp",
        delete=False  # No auto-delete, lo manejamos nosotros
    )
    
    try:
        async with aiofiles.open(tmp_file.name, 'wb') as tmp_file_async:
            for chunk in file_obj.chunks():
                await tmp_file_async.write(chunk)
        
        tmp_path = Path(tmp_file.name)
        logger.info("Temporary file created: %s (size: %s bytes)", 
                   tmp_path, tmp_path.stat().st_size)
        
        return tmp_path

    except Exception as exc:
        raise exc
    finally:
        tmp_file.close()
        Path(temp_dir, tmp_file.name).unlink(missing_ok=True)
        

async def cleanup_temp_file(file_path: Path):
    
    """Cleanup a temporary file created by save_uploaded_file_temporarily.

    This function is safe to call even if the file does not exist, as it will
    return None in that case.

    If the file exists and is a file, it will be unlinked and a debug log
    message will be emitted. If the file exists but is not a file (e.g. a directory),
    a warning log message will be emitted.

    If an OSError or PermissionError occurs during cleanup, an error log
    message will be emitted with the exception details. In container environments,
    we might not have permissions to cleanup the file, so this exception is
    expected and the OS will eventually clean it up.
    """
    if not file_path.exists():
        return None
    try:
        # Verificar que el archivo existe y es un archivo (no directorio)
        if file_path.exists() and file_path.is_file():
            file_path.unlink()
            logger.debug("Temporary file cleaned up: %s", file_path)
        elif file_path.exists():
            logger.warning("Path exists but is not a file: %s", file_path)
    except (OSError, PermissionError) as exc:
        logger.error("Failed to cleanup temporary file %s: %s", file_path, exc)
        # In container environments, we might not have permissions
        # The OS will clean it up eventually


@retry(
    stop=stop_after_attempt(3),
    wait=wait_fixed(0.5),
    retry=retry_if_exception_type((OSError, PermissionError)),
    before_sleep=before_sleep_log(logger, logging.WARNING),
)
async def create_tmp_file(file_obj, filename: str, video_id: str) -> Path:
    """Crea archivo temporal con reintentos."""
    tmp_path = await save_uploaded_file_temporarily(file_obj, filename)
    if not tmp_path:
        raise ValueError("Temporary file creation returned None")
    size = tmp_path.stat().st_size
    if size <= 0:
        raise ValueError(f"Invalid file size: {size}")
    logger.info("Temporary file ready", extra={"video_id": video_id, "size": size})
    return tmp_path

