from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    openai_api_key: str = Field(..., alias="OPENAI_API_KEY")
    openai_model: str = Field("gpt-4o-mini", alias="OPENAI_MODEL")

    temporal_address: str = Field("host.docker.internal:7233", alias="TEMPORAL_ADDRESS")
    temporal_namespace: str = Field("default", alias="TEMPORAL_NAMESPACE")
    temporal_task_queue: str = Field("stock-agent", alias="TEMPORAL_TASK_QUEUE")

    data_mode: str = Field("mock", alias="DATA_MODE")  # "mock" | "live"
    tick_seconds: int = Field(10, alias="TICK_SECONDS")
    drift_threshold: float = Field(0.20, alias="DRIFT_THRESHOLD")
    approval_threshold_usd: float = Field(10000.0, alias="APPROVAL_THRESHOLD_USD")
    num_sandboxes: int = Field(8, alias="NUM_SANDBOXES")

    mockoon_base_url: str = Field("http://mockoon:3001", alias="MOCKOON_BASE_URL")
    fastapi_internal_url: str = Field("http://fastapi:8000", alias="FASTAPI_INTERNAL_URL")
    fastapi_internal_token: str = Field("demo-token-change-me", alias="FASTAPI_INTERNAL_TOKEN")

    sandbox_image: str = Field("durable-agent-sandbox:latest", alias="SANDBOX_IMAGE")
    sandbox_network_disabled: bool = Field(True, alias="SANDBOX_NETWORK_DISABLED")
    log_level: str = Field("INFO", alias="LOG_LEVEL")


settings = Settings()
