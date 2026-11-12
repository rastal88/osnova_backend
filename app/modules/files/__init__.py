"""Files module: upload, list, download and delete files of signed-in users.

Enabled by FILES_ENABLED. Requires the auth module. Contents go to the storage
chosen by FILES_STORAGE (storage.py: local disk or an S3-compatible bucket),
metadata to the `files` table. Settings: FILES_*, S3_*.
Requirements: requirements/files.txt (no extra packages for S3)
"""

from fastapi import FastAPI


def register(app: FastAPI):
    from app.config import config
    from app.modules.auth.hooks import on_user_delete

    if config.APP_PROFILE == "scalable" and config.FILES_STORAGE == "local":
        # Each replica would see only the files uploaded through it
        raise RuntimeError(
            "APP_PROFILE=scalable needs FILES_STORAGE=s3: local files stay in one replica"
        )

    from .routes import delete_user_files, files_router

    on_user_delete(delete_user_files)

    app.include_router(files_router, prefix="/api/v1/files", tags=["Files"])
    return None
