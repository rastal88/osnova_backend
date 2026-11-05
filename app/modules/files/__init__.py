"""Files module: upload (authenticated) and download, stored on local disk.

Enabled by FILES_ENABLED. Requires the auth module.
Settings: FILES_DIR, FILES_MAX_SIZE_MB. Requirements: requirements/files.txt
"""

from fastapi import FastAPI


def register(app: FastAPI):
    from .routes import file_flow_router

    app.include_router(file_flow_router, prefix="/api/v1/file_flow", tags=["Files"])
    return None
