import os
from dataclasses import dataclass


def _required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


@dataclass(frozen=True)
class Settings:
    telegram_bot_token: str
    azure_openai_api_key: str
    azure_openai_endpoint: str
    azure_openai_deployment: str
    telegram_message_limit: int = 4000
    arxiv_min_text_length: int = 300
    generic_min_text_length: int = 500
    korean_ratio_threshold: float = 0.30

    @property
    def telegram_api_base(self) -> str:
        return f"https://api.telegram.org/bot{self.telegram_bot_token}"

    @property
    def azure_openai_base_url(self) -> str:
        return f"{self.azure_openai_endpoint.rstrip('/')}/openai/v1/"


def load_settings() -> Settings:
    return Settings(
        telegram_bot_token=_required_env("TELEGRAM_BOT_TOKEN"),
        azure_openai_api_key=_required_env("AZURE_OPENAI_API_KEY"),
        azure_openai_endpoint=_required_env("AZURE_OPENAI_ENDPOINT"),
        azure_openai_deployment=_required_env("AZURE_OPENAI_DEPLOYMENT"),
    )


settings = load_settings()

