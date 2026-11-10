"""Files of signed-in users: upload, list, download, delete.

Only the owner and admin roles reach a file. Contents are served as a download
(`attachment`, `application/octet-stream`) except for safe image types, so an
uploaded HTML or SVG never runs as a page of this site.
"""

import hashlib
import re
import uuid
from datetime import datetime
from pathlib import Path
from tempfile import SpooledTemporaryFile

from fastapi import APIRouter, Depends, File, Query, Response, UploadFile
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import config
from app.core.errors import AppError
from app.modules.auth.dependencies import current_user
from app.modules.auth.models import User
from app.modules.auth.roles import ADMIN_ROLES
from app.modules.db import get_async_session
from app.modules.files.models import FileRecord
from app.modules.files.storage import get_storage

files_router = APIRouter(dependencies=[Depends(current_user)])

MAX_SIZE = config.FILES_MAX_SIZE_MB * 1024 * 1024
CHUNK_SIZE = 1024 * 1024
# Kept in memory up to this size, then in a temporary file
SPOOL_SIZE = 1024 * 1024
CONTENT_TYPE = re.compile(r"^[a-z0-9][a-z0-9.+-]*/[a-z0-9][a-z0-9.+-]*$")
# Shown in the browser; everything else is downloaded
INLINE_TYPES = {"image/png", "image/jpeg", "image/gif", "image/webp", "image/avif"}
ALLOWED = tuple(item.strip() for item in config.FILES_ALLOWED_TYPES.split(",") if item.strip())


class FileRead(BaseModel):
    id: uuid.UUID
    name: str
    content_type: str
    size: int
    created_at: datetime
    url: str


class FilePage(BaseModel):
    items: list[FileRead]
    total: int


def read(file: FileRecord) -> FileRead:
    return FileRead(
        id=file.id,
        name=file.name,
        content_type=file.content_type,
        size=file.size,
        created_at=file.created_at,
        url=f"/api/v1/files/{file.id}",
    )


def _content_type(upload: UploadFile) -> str:
    value = (upload.content_type or "").split(";")[0].strip().lower()
    return value if CONTENT_TYPE.fullmatch(value) else "application/octet-stream"


def _name(upload: UploadFile) -> str:
    # Only the last part of a path, without control characters
    name = Path((upload.filename or "").replace("\\", "/")).name
    name = re.sub(r"[\x00-\x1f\x7f]", "", name).strip()
    return name[:255] or "file"


@files_router.post("", status_code=201)
async def upload_file(
    file: UploadFile = File(...),
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_async_session),
) -> FileRead:
    content_type = _content_type(file)
    if ALLOWED and not any(content_type.startswith(item) for item in ALLOWED):
        raise AppError(415, "file_type_not_allowed")

    size = 0
    digest = hashlib.sha256()
    with SpooledTemporaryFile(max_size=SPOOL_SIZE) as buffer:
        while chunk := await file.read(CHUNK_SIZE):
            size += len(chunk)
            if size > MAX_SIZE:
                raise AppError(413, "file_too_large", max_mb=config.FILES_MAX_SIZE_MB)
            digest.update(chunk)
            buffer.write(chunk)

        key = uuid.uuid4().hex
        await get_storage().save(key, buffer, size, digest.hexdigest(), content_type)

    record = FileRecord(
        owner_id=user.id, name=_name(file), content_type=content_type, size=size, key=key
    )
    session.add(record)
    await session.commit()
    return read(record)


@files_router.get("")
async def list_files(
    q: str = Query("", max_length=100, description="Part of the file name"),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_async_session),
) -> FilePage:
    """The signed-in user's files, newest first."""
    conditions = [FileRecord.owner_id == user.id]
    if search := q.strip():
        escaped = search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        conditions.append(FileRecord.name.ilike(f"%{escaped}%", escape="\\"))
    total = await session.scalar(select(func.count()).select_from(FileRecord).where(*conditions))
    rows = await session.scalars(
        select(FileRecord)
        .where(*conditions)
        .order_by(FileRecord.created_at.desc())
        .offset((page - 1) * size)
        .limit(size)
    )
    return FilePage(items=[read(file) for file in rows], total=total or 0)


async def _own_file(file_id: uuid.UUID, user: User, session: AsyncSession) -> FileRecord:
    file = await session.get(FileRecord, file_id)
    if file is None or (file.owner_id != user.id and user.role not in ADMIN_ROLES):
        # Same answer for someone else's file: its existence is not revealed
        raise AppError(404, "file_not_found")
    return file


@files_router.get("/{file_id}")
async def download_file(
    file_id: uuid.UUID,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_async_session),
) -> Response:
    """The contents (local storage) or a redirect to a short-lived bucket link (S3)."""
    file = await _own_file(file_id, user, session)
    response = await get_storage().response(file, inline=file.content_type in INLINE_TYPES)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Cache-Control"] = "private, no-store"
    return response


async def delete_user_files(session: AsyncSession, user: User) -> None:
    """Account deletion (app/modules/auth/hooks.py): contents first, then the rows."""
    storage = get_storage()
    for file in await session.scalars(select(FileRecord).where(FileRecord.owner_id == user.id)):
        await storage.delete(file.key)
        await session.delete(file)
    await session.flush()


@files_router.delete("/{file_id}", status_code=204)
async def delete_file(
    file_id: uuid.UUID,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_async_session),
) -> Response:
    file = await _own_file(file_id, user, session)
    await get_storage().delete(file.key)
    await session.delete(file)
    await session.commit()
    return Response(status_code=204)
