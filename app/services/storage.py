import re
import shutil
import zipfile
from pathlib import Path

from defusedxml import ElementTree
from fastapi import UploadFile

from app.core.config import Settings

_FILENAME_RE = re.compile(r"[^A-Za-z0-9._-]+")


class StorageLimitError(ValueError):
    pass


class UploadValidationError(ValueError):
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


def validate_saved_upload(path: Path, file_type: str) -> None:
    if file_type == "shapefile-zip":
        if not zipfile.is_zipfile(path):
            raise UploadValidationError("Uploaded .zip file is not a valid ZIP archive.")
        return

    if file_type != "kml":
        raise UploadValidationError("Unsupported file type.")

    try:
        root = ElementTree.parse(path).getroot()
    except Exception as exc:
        raise UploadValidationError("Uploaded KML is not valid XML.") from exc

    local_name = root.tag.rsplit("}", 1)[-1].lower()
    if local_name != "kml":
        raise UploadValidationError("Uploaded XML document is not a KML document.")


def safe_filename(filename: str | None) -> str:
    raw = Path(filename or "upload").name
    cleaned = _FILENAME_RE.sub("_", raw).strip(".")
    return cleaned or "upload"


def remove_upload(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path.parent, ignore_errors=True)
