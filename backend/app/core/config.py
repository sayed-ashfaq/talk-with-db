from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    groq_api_key: str

    # one model id per agent, so each can be tuned independently
    main_agent_model: str = "llama-3.3-70b-versatile"
    sql_agent_model: str = "openai/gpt-oss-120b"


settings = Settings()
