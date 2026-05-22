from temporalio.client import Client
from temporalio.contrib.pydantic import pydantic_data_converter
from shared.settings import settings

_client: Client | None = None


async def get_temporal_client() -> Client:
    global _client
    if _client is None:
        _client = await Client.connect(
            settings.temporal_address,
            namespace=settings.temporal_namespace,
            data_converter=pydantic_data_converter,
        )
    return _client
