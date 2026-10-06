import re
from pathlib import Path

from fastapi import UploadFile

from app.core.config import Settings

_FILENAME_RE = re.compile(r"[^A-Za-z0-9._-]+")


class StorageLimitError(ValueError):
    pass


async def save_upload(upload: UploadFile, destination: Path, settings: Settings) -> int:
    destination.parent.mkdir(parents=True, exist_ok=True)
    total = 0
    try:
        with destination.open("wb") as output:
            while chunk := await upload.read(1024 * 1024):
                total += len(chunk)
                if total > settings.max_upload_size_bytes:
                    raise StorageLimitError(
                        f"Uploaded file exceeds the {settings.max_upload_size_mb} MB limit."
                    )
                output.write(chunk)
    except Exception:
        destination.unlink(missing_ok=True)
        raise
    finally:
        await upload.close()
    return total


def safe_filename(filename: str | None) -> str:
    raw = Path(filename or "upload").name
    cleaned = _FILENAME_RE.sub("_", raw).strip(".")
    return cleaned or "upload"
