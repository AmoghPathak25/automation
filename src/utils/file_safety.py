from __future__ import annotations
import hashlib
import os
import tempfile
from pathlib import Path
from typing import Callable
ALLOWED_EXTENSIONS = {".xlsx", ".xlsm", ".csv", ".pdf", ".txt", ".eml"}

def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()

def validate_file(path: str | Path, max_bytes: int = 50 * 1024 * 1024) -> None:
    source = Path(path)
    if source.suffix.lower() not in ALLOWED_EXTENSIONS:
        raise ValueError(f"Unsupported file type: {source.suffix or '(no extension)'}")
    if not source.is_file():
        raise ValueError("The selected input is not a readable file.")
    if source.stat().st_size > max_bytes:
        raise ValueError(f"File exceeds the configured limit of {max_bytes // (1024 * 1024)} MB.")

def atomic_write(destination: str | Path, writer: Callable[[Path], None]) -> Path:
    target = Path(destination)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{target.stem}_", suffix=target.suffix, dir=target.parent)
    os.close(fd)
    temp_path = Path(temporary)
    try:
        writer(temp_path)
        os.replace(temp_path, target)
    except Exception:
        temp_path.unlink(missing_ok=True)
        raise
    return target
