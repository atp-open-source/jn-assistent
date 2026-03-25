import os
from dataclasses import dataclass, field
from pydantic import BaseModel


class Metadata(BaseModel):
    """
    Metadata for an audio recording session, sent as JSON alongside raw audio chunks.
    """

    call_id: str
    agent_id: str
    koe_id: str
    status: str
    channels: int
    sample_width: int
    frame_rate: int
    speaker: str
    cpr: str = ""


@dataclass
class BaseConfig:
    """Base configuration shared by all environments."""

    ENV: str = "prod"
    LEVERANCE_URL: str = field(
        default_factory=lambda: os.getenv("LEVERANCE_URL", "https://leverance")
    )
    LEVERANCE_URL_PROCESS_CALL: str = field(
        default_factory=lambda: os.getenv(
            "LEVERANCE_URL_PROCESS_CALL",
            f"{os.getenv('LEVERANCE_URL', 'https://leverance')}/process_call",
        )
    )
    LEVERANCE_URL_STA_CREDENTIALS: str = field(
        default_factory=lambda: os.getenv(
            "LEVERANCE_URL_STA_CREDENTIALS",
            f"{os.getenv('LEVERANCE_URL', 'https://leverance')}/sta_credentials",
        )
    )
    BLOB_ACCOUNT_URL: str = field(
        default_factory=lambda: os.getenv("BLOB_ACCOUNT_URL", "")
    )
    QUEUE_ACCOUNT_URL: str = field(
        default_factory=lambda: os.getenv("QUEUE_ACCOUNT_URL", "")
    )
    AZURE_OPENAI_ENDPOINT: str = field(
        default_factory=lambda: os.getenv("AZURE_OPENAI_ENDPOINT", "")
    )
    STORAGE_ACCOUNT_NAME: str = field(
        default_factory=lambda: os.getenv("STORAGE_ACCOUNT_NAME", "")
    )


@dataclass
class DevConfig(BaseConfig):
    """Development environment configuration."""

    ENV: str = "dev"
    LEVERANCE_URL: str = field(
        default_factory=lambda: os.getenv("LEVERANCE_URL", "https://localhost:5000")
    )
    LEVERANCE_URL_PROCESS_CALL: str = field(
        default_factory=lambda: os.getenv(
            "LEVERANCE_URL_PROCESS_CALL",
            f"{os.getenv('LEVERANCE_URL', 'https://localhost:5000')}/process_call",
        )
    )
    LEVERANCE_URL_STA_CREDENTIALS: str = field(
        default_factory=lambda: os.getenv(
            "LEVERANCE_URL_STA_CREDENTIALS",
            f"{os.getenv('LEVERANCE_URL', 'https://localhost:5000')}/sta_credentials",
        )
    )


@dataclass
class ProdConfig(BaseConfig):
    """Production environment configuration."""

    ENV: str = "prod"


def get_config(env: str = "prod", azure: bool = False) -> BaseConfig:
    """
    Return the appropriate config object for the given environment.

    :param env:   'dev' or 'prod'
    :param azure: Whether the controller is running in Azure (currently unused,
                  reserved for future environment-specific overrides).
    Returns: A BaseConfig subclass instance.
    """
    if env == "dev":
        return DevConfig()
    return ProdConfig()
