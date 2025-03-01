from pydantic_settings import BaseSettings
from app.core.settings import DATABASE

class Settings(BaseSettings):
    DATABASE_URL: str = (
        f"postgresql://{DATABASE['USER']}:{DATABASE['PASSWORD']}@"
        f"{DATABASE['HOST']}:{DATABASE['PORT']}/{DATABASE['NAME']}"
    )

settings = Settings()