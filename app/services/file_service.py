import os
import base64
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from PIL import Image
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename

from app.errors import AppError

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}


class FileService:
    @staticmethod
    def _is_allowed(filename):
        return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

    @classmethod
    def save_image(cls, storage: FileStorage, upload_root: str):
        if not storage or not storage.filename:
            return None

        filename = secure_filename(storage.filename)
        if not filename or not cls._is_allowed(filename):
            raise AppError("Unsupported image format.", 400)

        # Verify actual image bytes to avoid extension spoofing.
        try:
            img = Image.open(storage.stream)
            img.verify()
            storage.stream.seek(0)
        except Exception as exc:
            raise AppError("Invalid image file.", 400) from exc

        dated_folder = datetime.utcnow().strftime("%Y/%m/%d")
        folder = Path(upload_root) / dated_folder
        folder.mkdir(parents=True, exist_ok=True)

        extension = filename.rsplit(".", 1)[1].lower()
        unique_filename = f"{uuid4().hex}.{extension}"
        absolute_path = folder / unique_filename
        storage.save(absolute_path)

        return str(Path(upload_root).name + "/" + dated_folder + "/" + unique_filename)

    @classmethod
    def save_camera_data_url(cls, data_url: str, upload_root: str):
        if not data_url or "base64," not in data_url:
            return None
        try:
            header, encoded = data_url.split("base64,", 1)
            if "image/jpeg" in header:
                extension = "jpg"
            elif "image/webp" in header:
                extension = "webp"
            else:
                extension = "png"

            dated_folder = datetime.utcnow().strftime("%Y/%m/%d")
            folder = Path(upload_root) / dated_folder
            folder.mkdir(parents=True, exist_ok=True)

            unique_filename = f"{uuid4().hex}.{extension}"
            absolute_path = folder / unique_filename
            absolute_path.write_bytes(base64.b64decode(encoded))
            return str(Path(upload_root).name + "/" + dated_folder + "/" + unique_filename)
        except Exception as exc:
            raise AppError("Invalid camera image payload.", 400) from exc
