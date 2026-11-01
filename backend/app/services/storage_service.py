import mimetypes
import uuid
from io import BytesIO
from pathlib import Path

import boto3
from PIL import Image, UnidentifiedImageError

from app.config import settings


def validate_image(data: bytes, content_type: str) -> None:
    formats = {"image/jpeg": "JPEG", "image/png": "PNG", "image/webp": "WEBP"}
    if content_type not in formats:
        raise ValueError("Upload a JPEG, PNG, or WebP image")
    try:
        with Image.open(BytesIO(data)) as image:
            if image.format != formats[content_type]:
                raise ValueError("Image content does not match its declared file type")
            if image.width * image.height > 40_000_000:
                raise ValueError("Image exceeds the 40-megapixel limit")
            image.verify()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise ValueError("The uploaded file is not a valid supported image") from exc


def store_image(data: bytes, filename: str, content_type: str) -> str:
    key = f"reports/{uuid.uuid4().hex}{Path(filename).suffix.lower()}"
    if settings.aws_s3_bucket:
        client = boto3.client("s3", region_name=settings.aws_region,
            aws_access_key_id=settings.aws_access_key_id or None,
            aws_secret_access_key=settings.aws_secret_access_key or None)
        client.put_object(Bucket=settings.aws_s3_bucket, Key=key, Body=data,
            ContentType=content_type or mimetypes.guess_type(filename)[0] or "application/octet-stream")
        return f"https://{settings.aws_s3_bucket}.s3.{settings.aws_region}.amazonaws.com/{key}"
    directory = Path(settings.storage_dir)
    directory.mkdir(parents=True, exist_ok=True)
    destination = directory / Path(key).name
    destination.write_bytes(data)
    return f"/uploads/{destination.name}"
