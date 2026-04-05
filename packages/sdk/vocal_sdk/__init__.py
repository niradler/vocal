__version__ = "0.3.8"
"""Vocal SDK — Python client for the Vocal Speech AI Platform.

Auto-generated from the Vocal OpenAPI specification using openapi-python-client.
Do not edit directly — run ``make generate-sdk`` to regenerate.

Quick start::

    from vocal_sdk import VocalClient
    from vocal_sdk.api.models import list_models_v1_models_get
    from vocal_sdk.api.transcription import create_transcription_v1_audio_transcriptions_post

    client = VocalClient(base_url="http://localhost:8000")

    # Async usage
    import asyncio

    async def main():
        result = await create_transcription_v1_audio_transcriptions_post.asyncio(client=client, ...)
        print(result.text)

    asyncio.run(main())
"""

from .client import VocalAuthenticatedClient, VocalClient

__all__ = (
    "VocalAuthenticatedClient",
    "VocalClient",
)

from .compat import VocalSDK

__all__ = __all__ + ("VocalSDK",)
