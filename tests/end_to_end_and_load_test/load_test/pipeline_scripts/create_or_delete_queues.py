import argparse
import asyncio
import os

from azure.identity.aio import DefaultAzureCredential
from azure.storage.queue.aio import QueueServiceClient
from azure.core.exceptions import ResourceExistsError, ResourceNotFoundError
from loguru import logger

from audio_streamer.config import get_config

_ACTION_CREATE = "create"
_ACTION_DELETE = "delete"


def get_queue_service_client(
    account_name: str, credential: DefaultAzureCredential
) -> QueueServiceClient:
    """
    Opret asynkron QueueServiceClient til den angivne storage-konto med de givne
    legitimationsoplysninger.
    """

    if not account_name:
        logger.error("FEJL: account_name er ikke sat.")
        raise ValueError("account_name er ikke sat")
    return QueueServiceClient(
        f"https://{account_name}.queue.core.windows.net", credential=credential
    )


async def process_status_queues(
    queue_service_client: QueueServiceClient,
    total: int,
    action: str,
    semaphore_limit: int = 50,
) -> None:
    """
    Opret eller slet statuskøer i storage-kontoen.

    Er defineret som en asynkron funktion for at kunne oprette/slette køer parallelt.
    """

    if total <= 0:
        logger.error("Ingen køer at behandle (antal <= 0).")
        return
    elif total > 1000:
        logger.warning(f"{total} køer anmodet. Sætter til maksimum på 1000.")
        total = 1000

    semaphore = asyncio.Semaphore(semaphore_limit)

    async def operate_on_queue(index: int) -> None:
        """Opret eller slet statuskøen med det givne indeks."""

        queue_name = f"status-l{index:03d}"
        async with semaphore:
            queue_client = queue_service_client.get_queue_client(queue_name)
            try:
                if action == _ACTION_CREATE:
                    await queue_client.create_queue()
                    logger.info(f"Oprettet kø: {queue_name}")
                else:
                    await queue_client.delete_queue()
                    logger.info(f"Slettet kø: {queue_name}")
            except ResourceExistsError:
                if action == _ACTION_CREATE:
                    logger.info(f"Kø findes allerede: {queue_name}")
                else:
                    raise
            except ResourceNotFoundError:
                if action == _ACTION_DELETE:
                    logger.info(f"Kø ikke fundet: {queue_name}")
                else:
                    raise
            except Exception as exc:
                logger.exception(f"Fejl ved {action} af kø {queue_name}: {exc}")
                raise
            finally:
                await queue_client.close()

    tasks: list[asyncio.Task[None]] = []
    for index in range(total):
        tasks.append(asyncio.create_task(operate_on_queue(index)))

    if tasks:
        results = await asyncio.gather(*tasks, return_exceptions=True)
        errors = [result for result in results if isinstance(result, Exception)]
        if errors:
            raise errors[0]


async def _async_main(action: str, n_queues: int, env: str) -> int:
    """Asynkron main-funktion til oprettelse/sletning af køer."""

    config = get_config(env=env.lower())

    try:
        async with DefaultAzureCredential() as credential:
            queue_service_client = get_queue_service_client(
                config.STORAGE_ACCOUNT_NAME, credential
            )
            try:
                await process_status_queues(queue_service_client, n_queues, action)
            finally:
                await queue_service_client.close()
    except Exception as exc:
        logger.exception(f"Kø {action} fejlede: {exc}")
        return 1
    return 0


def _parse_args() -> tuple[str, int, str]:
    """Parse kommandolinjeargumenter for handlingstype, antal køer og miljø."""

    parser = argparse.ArgumentParser(
        description="Opret eller slet statuskøer i den angivne miljøkonfigurations storage-konto."
    )
    parser.add_argument(
        "action",
        choices=(_ACTION_CREATE, _ACTION_DELETE),
        help=f"Kø-operation der skal udføres. Tilladte værdier: {_ACTION_CREATE}, {_ACTION_DELETE}.",
    )
    parser.add_argument(
        "-n",
        "--n-queues",
        type=int,
        default=10,
        help="Antal køer der skal oprettes eller slettes (standard: 10).",
    )
    parser.add_argument(
        "-e",
        "--env",
        type=str,
        choices=("dev", "prod"),
        help="Miljøkonfiguration der skal bruges (standard: dev).",
        default="dev",
    )
    args = parser.parse_args()
    return args.action, args.n_queues, args.env


def main() -> int:
    action, n_queues, env = _parse_args()
    return asyncio.run(_async_main(action, n_queues, env))


if __name__ == "__main__":
    main()
