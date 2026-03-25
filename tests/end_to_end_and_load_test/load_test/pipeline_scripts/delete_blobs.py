import argparse
import asyncio
import os

from azure.identity.aio import DefaultAzureCredential
from azure.storage.blob.aio import BlobServiceClient
from azure.core.exceptions import ResourceExistsError
from loguru import logger

from audio_streamer.config import get_config


def get_blob_service_client(
    account_name: str, credential: DefaultAzureCredential
) -> BlobServiceClient:
    """
    Opret asynkron BlobServiceClient til den angivne storage-konto med de givne
    legitimationsoplysninger.
    """

    if not account_name:
        logger.error("FEJL: account_name er ikke sat.")
        raise ValueError("account_name er ikke sat")
    return BlobServiceClient(
        f"https://{account_name}.blob.core.windows.net", credential=credential
    )


async def delete_blobs_in_container(
    blob_service_client: BlobServiceClient,
    container_name: str,
    prefix: str = "",
    semaphore_limit: int = 50,
) -> None:
    """
    Slet alle blobs i den angivne container med det angivne præfiks.

    Er defineret som en asynkron funktion for at kunne slette blobs parallelt.
    """

    container_client = blob_service_client.get_container_client(container_name)

    try:
        semaphore = asyncio.Semaphore(semaphore_limit)

        async def delete_blob_task(blob_name: str) -> None:
            """Slet den angivne blob."""
            async with semaphore:
                try:
                    await container_client.delete_blob(blob_name)
                    logger.info(f"Slettet blob: {blob_name}")
                except Exception as exc:
                    logger.exception(f"Kunne ikke slette blob {blob_name}: {exc}")

        tasks: list[asyncio.Task[None]] = []
        async for blob in container_client.list_blobs(name_starts_with=prefix):
            tasks.append(asyncio.create_task(delete_blob_task(blob.name)))

        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            errors = [result for result in results if isinstance(result, Exception)]
            if errors:
                raise errors[0]

    except ResourceExistsError:
        logger.info(f"Container findes ikke: {container_name}")
    finally:
        await container_client.close()


async def _async_main(env: str, container: str, prefix: str) -> int:
    """Asynkron main-funktion til sletning af blobs."""

    config = get_config(env=env.lower())

    try:
        async with DefaultAzureCredential() as credential:
            blob_service_client = get_blob_service_client(
                config.STORAGE_ACCOUNT_NAME, credential
            )
            try:
                await delete_blobs_in_container(blob_service_client, container, prefix)
            finally:
                await blob_service_client.close()
    except Exception as e:
        logger.exception(f"Blob sletning fejlede: {e}")
        return 1
    return 0


def _parse_args() -> tuple[str, str, str]:
    """Parse kommandolinjeargumenter for miljø, container og præfiks."""

    parser = argparse.ArgumentParser(
        description="Slet blobs i den angivne miljøkonfigurations storage-konto."
    )
    parser.add_argument(
        "-e",
        "--env",
        type=str,
        choices=("dev", "prod"),
        help="Miljøkonfiguration der skal bruges (standard: dev).",
        default="dev",
    )
    parser.add_argument(
        "-c",
        "--container",
        type=str,
        help="Navn på containeren der skal slettes blobs fra (standard: 'transcriptions').",
        default="transcriptions",
    )
    parser.add_argument(
        "-p",
        "--prefix",
        type=str,
        help="Præfiks for blobs der skal slettes (standard: 'transcriptions-loadtest').",
        default="transcriptions-loadtest",
    )
    args = parser.parse_args()
    return args.env, args.container, args.prefix


def main() -> int:
    env, container, prefix = _parse_args()
    return asyncio.run(_async_main(env, container, prefix))


if __name__ == "__main__":
    main()
