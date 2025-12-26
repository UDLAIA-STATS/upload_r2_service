from datetime import timezone
import datetime
from io import BytesIO
import boto3
from decouple import config
from botocore.client import Config
import logging

logger = logging.getLogger("app")  # usa el logger de tu proyecto


s3_client = boto3.client(
    "s3",
    endpoint_url=config("S3_CLIENT_ACCOUNT_ENDPOINT"),
    aws_access_key_id=config("R2_ACCESS_KEY_ID"),
    aws_secret_access_key=config("R2_SECRET_ACCESS_KEY"),
    region_name="auto"
)


def upload_video_file(filename: str, file_bytes: bytes, id_partido: str):
    logger.info("Iniciando proceso de subida de video...")

    timestamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d%H%M%S")
    key = f"{id_partido}/{timestamp}_{filename}"

    logger.debug(f"Filename recibido: {filename}")
    logger.debug(f"ID del partido: {id_partido}")
    logger.debug(f"Key generada para R2: {key}")
    logger.debug(f"Tamaño del archivo recibido: {len(file_bytes)} bytes")

    upload(key, file_bytes)


def upload(key: str, file_bytes: bytes):
    logger.info("Preparando envío a Cloudflare R2...")
    logger.debug(f"Bucket destino: {config('R2_BUCKET')}")
    logger.debug(f"Key destino: {key}")

    try:
        logger.info("Subiendo archivo a R2...")
        s3_client.upload_fileobj(
            Fileobj=BytesIO(file_bytes),
            Bucket=config("R2_BUCKET"),
            Key=key,
            ExtraArgs={"ContentType": "video/mp4"}
        )
        logger.info(f"Archivo subido correctamente a R2: {key}")

    except Exception as e:
        logger.error(f"Error subiendo archivo a R2: {e}")
        raise e

def get_metadata(key: str):
    try:
        response = s3_client.head_object(
            Bucket=config("R2_BUCKET"),
            Key=key
        )
        return response
    except Exception as e:
        logger.error(f"Error obteniendo metadata de R2 para {key}: {e}")
        raise e
