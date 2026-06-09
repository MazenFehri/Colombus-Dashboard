from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    database_url: str = "sqlite:///./fx_dashboard.db"
    groq_api_key: str = ""

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8-sig",
        "extra": "ignore",
    }

settings = Settings()
