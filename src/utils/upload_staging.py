from __future__ import annotations
import logging
import shutil
import tempfile
from pathlib import Path
from uuid import uuid4
logger = logging.getLogger("father_automation")


def safe_upload_basename(filename: str) -> str:
    # Return only a plain filename; discard client-supplied path components.
    name = str(filename or "upload")
    # Treat both Windows and POSIX separators as path delimiters on every platform.
    name = name.replace("\\", "/").split("/")[-1]
    name = Path(name).name
    if name in {"", ".", ".."}:
        return "upload"
    return name
class StagedUpload:
    # Unique temporary upload area; only its owned directory is removed on exit.
    @staticmethod
    def safe_name(filename: str) -> str:
        return safe_upload_basename(filename)
    def __init__(self, staging_root: str | Path, filename: str, content: bytes):
        self.root = Path(staging_root).resolve()
        self.filename = safe_upload_basename(filename)
        self.content = content
        self.directory: Path | None = None
        self.path: Path | None = None
    def __enter__(self) -> "StagedUpload":
        self.root.mkdir(parents=True, exist_ok=True)
        self.directory = Path(tempfile.mkdtemp(prefix=f"upload_{uuid4().hex}_", dir=self.root)).resolve()
        self.path = (self.directory / self.filename).resolve()
        if self.directory not in self.path.parents:
            shutil.rmtree(self.directory, ignore_errors=True)
            raise ValueError("Unsafe upload filename could not be contained in the staging directory.")
        try:
            self.path.write_bytes(self.content)
        except Exception:
            self.cleanup()
            raise
        return self
    def cleanup(self) -> None:
        if self.directory is None:
            return
        try:
            shutil.rmtree(self.directory)
        except FileNotFoundError:
            pass
        except Exception as exc:  # cleanup must never mask a processing exception
            logger.warning("Temporary upload cleanup failed (%s).", type(exc).__name__)
        finally:
            self.directory = None
            self.path = None
    def __exit__(self, exc_type, exc_value, traceback) -> bool:
        self.cleanup()
        return False
