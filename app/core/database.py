from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core import settings

def init_db(app):

    DATABASE_URL = settings.DATABASE_URL
    engine = create_engine(DATABASE_URL)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


    from alembic import command
    from alembic.config import Config as AlembicConfig
    alembic_cfg = AlembicConfig("alembic.ini")
    command.upgrade(alembic_cfg, "head")

    return SessionLocal