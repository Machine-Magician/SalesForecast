import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    """Глобальные настройки приложения."""
    
    # Какой платёжный шлюз используем
    GATEWAY: str = os.getenv("GATEWAY", "cloudpayments")

    # Ключи CloudPayments
    CP_PUBLIC_ID: str = os.getenv("CP_PUBLIC_ID", "")
    CP_API_SECRET: str = os.getenv("CP_API_SECRET", "")

    # Приложение
    APP_TITLE: str = os.getenv("APP_TITLE", "Platform API")
    DEBUG: bool = os.getenv("DEBUG", "true").lower() == "true"


settings = Settings()
