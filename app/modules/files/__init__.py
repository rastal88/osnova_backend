"""Files module: upload, list, download and delete files of signed-in users.

Enabled by FILES_ENABLED. Requires the auth module. Contents go to the storage
chosen by FILES_STORAGE (storage.py: local disk or an S3-compatible bucket),
metadata to the `files` table. Settings: FILES_*, S3_*.
Requirements: requirements/files.txt (no extra packages for S3)
"""

from fastapi import FastAPI


def register(app: FastAPI):
    from .routes import files_router

    app.include_router(files_router, prefix="/api/v1/files", tags=["Files"])
    return None
