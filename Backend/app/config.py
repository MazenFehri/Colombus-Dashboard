from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    database_url: str = "sqlite:///./fx_dashboard.db"
    groq_api_key: str = ""
    gnews_api_key: str = ""  # optional fallback news provider; no-ops when unset

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8-sig",
        "extra": "ignore",
    }

settings = Settings()
