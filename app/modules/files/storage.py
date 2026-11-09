"""Where file contents live: FILES_STORAGE=local (FILES_DIR) or s3 (S3_* settings).

A storage keeps bytes under a key chosen by the server and gives them back as
a response. To add another backend (e.g. a CDN), implement Storage and pick it
in ``get_storage``. Metadata (owner, name, size) is in the database (models.py).
"""

import shutil
from functools import cache
from pathlib import Path
from tempfile import SpooledTemporaryFile
from typing import Protocol
from urllib.parse import quote

from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, RedirectResponse, Response

from app.config import config
from app.modules.files.s3 import S3Client


class StoredFile(Protocol):
    key: str
    name: str
    content_type: str


class Storage(Protocol):
    async def save(
        self, key: str, upload: SpooledTemporaryFile, size: int, sha256: str, content_type: str
    ) -> None: ...

    async def response(self, file: StoredFile, inline: bool) -> Response: ...

    async def delete(self, key: str) -> None: ...


def content_disposition(name: str, inline: bool) -> str:
    """Original name for the browser; non-ASCII names per RFC 5987."""
    kind = "inline" if inline else "attachment"
    ascii_name = name.encode("ascii", "replace").decode().replace('"', "")
    return f"{kind}; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(name)}"


class LocalStorage:
    def __init__(self, root: Path) -> None:
        self.root = root

    def _path(self, key: str) -> Path:
        return self.root / key

    async def save(self, key, upload, size, sha256, content_type) -> None:
        def write() -> None:
            self.root.mkdir(parents=True, exist_ok=True)
            upload.seek(0)
            with self._path(key).open("wb") as target:
                shutil.copyfileobj(upload, target)

        await run_in_threadpool(write)

    async def response(self, file: StoredFile, inline: bool) -> Response:
        return FileResponse(
            self._path(file.key),
            media_type=file.content_type if inline else "application/octet-stream",
            headers={"Content-Disposition": content_disposition(file.name, inline)},
        )

    async def delete(self, key: str) -> None:
        self._path(key).unlink(missing_ok=True)


class S3Storage:
    def __init__(self, client: S3Client, link_seconds: int) -> None:
        self.client = client
        self.link_seconds = link_seconds

    async def save(self, key, upload, size, sha256, content_type) -> None:
        upload.seek(0)
        await run_in_threadpool(self.client.put, key, upload, size, sha256, content_type)

    async def response(self, file: StoredFile, inline: bool) -> Response:
        # The browser downloads straight from the bucket with a short-lived link
        content_type = file.content_type if inline else "application/octet-stream"
        url = self.client.presigned_get(
            file.key,
            self.link_seconds,
            {
                "response-content-disposition": content_disposition(file.name, inline),
                "response-content-type": content_type,
            },
        )
        return RedirectResponse(url, status_code=307)

    async def delete(self, key: str) -> None:
        await run_in_threadpool(self.client.delete, key)


@cache
def get_storage() -> Storage:
    if config.FILES_STORAGE == "s3":
        missing = [
            name
            for name in ("S3_ENDPOINT_URL", "S3_BUCKET", "S3_ACCESS_KEY", "S3_SECRET_KEY")
            if not getattr(config, name)
        ]
        if missing:
            raise RuntimeError(f"FILES_STORAGE=s3 requires {', '.join(missing)}")
        client = S3Client(
            config.S3_ENDPOINT_URL,  # type: ignore[arg-type]
            config.S3_BUCKET,  # type: ignore[arg-type]
            config.S3_REGION,
            config.S3_ACCESS_KEY,  # type: ignore[arg-type]
            config.S3_SECRET_KEY,  # type: ignore[arg-type]
        )
        return S3Storage(client, config.S3_LINK_SECONDS)
    return LocalStorage(Path(config.FILES_DIR))
