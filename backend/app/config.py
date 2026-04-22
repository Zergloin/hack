from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://app:changeme@db:5432/population_db"
    # For local dev without PostgreSQL, set DATABASE_URL=sqlite+aiosqlite:///./dev.db

    llm_provider: str = "openai"
    llm_api_key: str = ""
    llm_model: str = "gpt-4o"
    llm_base_url: str = ""

    data_dir: str = "data"

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
