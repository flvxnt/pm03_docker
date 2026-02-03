import os
import uuid
import hashlib
from fastapi import UploadFile

from app.core.config import settings


def ensure_storage():
    os.makedirs(settings.STORAGE_PATH, exist_ok=True)


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def save_upload(file: UploadFile) -> tuple[str, str, str]:
    """
    Возвращает:
    - stored_filename
    - full_path
    - sha256
    """
    ensure_storage()

    ext = ""
    if file.filename and "." in file.filename:
        ext = "." + file.filename.split(".")[-1]

    stored_filename = f"{uuid.uuid4().hex}{ext}"
    full_path = os.path.join(settings.STORAGE_PATH, stored_filename)

    # пишем файл на диск
    with open(full_path, "wb") as f:
        while True:
            chunk = file.file.read(1024 * 1024)
            if not chunk:
                break
            f.write(chunk)

    sha256 = sha256_file(full_path)
    return stored_filename, full_path, sha256
