from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    database_url: str = "sqlite:///./fx_dashboard.db"
    groq_api_key: str = ""

    # Auth
    jwt_secret: str = "dev-insecure-change-me"   # MUST be overridden in prod via .env
    jwt_expire_minutes: int = 10080              # 7 days

    # Email / SMTP (Gmail app password)
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""                          # falls back to smtp_user when empty

    # Daily digest schedule
    digest_hour: int = 8
    digest_timezone: str = "Africa/Tunis"

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8-sig",
        "extra": "ignore",
    }

settings = Settings()
