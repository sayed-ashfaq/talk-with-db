from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url

# drivers that mean "postgres, synchronously" — rewritten to asyncpg so .env can stay in the
# ordinary postgres:// form that psql and every other tool understands
_SYNC_POSTGRES_DRIVERS = {"postgresql", "postgres", "postgresql+psycopg2", "postgresql+psycopg"}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    groq_api_key: str

    # one model id per agent, so each can be tuned independently
    main_agent_model: str = "llama-3.3-70b-versatile"
    sql_agent_model: str = "openai/gpt-oss-120b"

    # app's own metadata store (saved DB connections), separate from any target DB
    metadata_database_url: str
    credentials_encryption_key: str

    @field_validator("metadata_database_url")
    @classmethod
    def _force_async_driver(cls, value: str) -> str:
        """Our metadata store is accessed only through the async engine, and asyncpg is the only
        driver that works there. Normalising here means one URL in .env instead of a sync copy for
        Alembic and an async copy for the app, which drift apart the moment one is edited."""
        url = make_url(value)
        if url.drivername in _SYNC_POSTGRES_DRIVERS:
            url = url.set(drivername="postgresql+asyncpg")
        return url.render_as_string(hide_password=False)


settings = Settings()
