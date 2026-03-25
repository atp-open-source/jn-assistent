import logging
import time
import csv
from pathlib import Path

from locust import events
from locust.env import Environment
from locust.runners import (
    STATE_CLEANUP,
    STATE_RUNNING,
    STATE_SPAWNING,
    STATE_STOPPED,
    STATE_STOPPING,
    MasterRunner,
    LocalRunner,
)
import gevent

from parameters import ACTIVE_CALLS_OUTPUT_PATH


def disable_insecure_request_warnings():
    """Deaktiverer InsecureRequestWarning globalt."""
    import urllib3

    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def register_listeners():
    """Registrerer Locust event listeners for load testen."""

    @events.init.add_listener
    def on_locust_init(environment, **kwargs):
        """
        Kaldes når Locust starter op.
        Opsætter monitorering af fejlrate og slår verbose logging fra for Azure SDK.
        """
        # Monitorer fejlraten og stop testen hvis den bliver for høj
        if isinstance(environment.runner, (MasterRunner, LocalRunner)):
            gevent.spawn(
                monitor_failure_rate,
                env=environment,
                max_fail_rate=0.05,
                min_denominator=100,
                check_interval=5.0,
            )

        # Slå verbose logging fra for Azure SDK
        for logger_name in [
            "azure.identity",
            "azure.core.pipeline.policies.http_logging_policy",
        ]:
            _logger = logging.getLogger(logger_name)
            _logger.setLevel(logging.WARNING)

    @events.test_start.add_listener
    def on_test_start(environment, **kwargs):
        """
        Kaldes når load testen starter.
        Starter monitorering af antal aktive opkald.
        """
        # Monitorer aktive opkald og gem historikken
        if isinstance(environment.runner, (MasterRunner, LocalRunner)):
            gevent.spawn(monitor_active_calls, env=environment, check_interval=5.0)

    @events.test_stop.add_listener
    def on_test_stop(environment, **kwargs):
        """
        Kaldes når load testen stopper.
        Gemmer historikken over aktive opkald til en CSV-fil.
        """
        # Gem aktive opkaldsdata når testen stopper
        if isinstance(environment.runner, (MasterRunner, LocalRunner)):
            save_active_calls_history(
                env=environment,
                output_file=Path(ACTIVE_CALLS_OUTPUT_PATH),
            )

    @events.usage_monitor.add_listener
    def on_usage_monitor(environment, cpu_usage, memory_usage, **kwargs):
        """
        Kaldes hver runners.CPU_MONITOR_INTERVAL sekunder (default 5 sekunder).
        Logger CPU- og hukommelsesforbrug, så vi kan holde øje med ressourceforbrug
        under testen.
        """
        # Log CPU og memory usage
        logging.info(f"CPU Usage: {cpu_usage:.2f}%, Memory Usage: {memory_usage} bytes")


def monitor_failure_rate(
    env: Environment,
    max_fail_rate: float = 0.05,
    min_denominator: int = 100,
    check_interval: float = 5.0,
) -> None:
    """
    Tjekker periodisk globale statistikker og stopper testen, hvis fejlraten
    overstiger max_fail_rate.
    Skal startes som en greenlet før testen starter.
    """

    while not env.runner.state in [STATE_STOPPING, STATE_STOPPED, STATE_CLEANUP]:
        gevent.sleep(check_interval)
        stats = env.stats.total
        num_requests = stats.num_requests
        num_failures = stats.num_failures
        fail_rate = num_failures / max(min_denominator, num_requests)
        if fail_rate > max_fail_rate:
            logging.warning(
                f"Fejlrate er for høj ({fail_rate:.3f} > {max_fail_rate}). Stopper testen..."
            )
            try:
                env.runner.quit()
                logging.info("Test stoppet pga. høj fejlrate.")
            except Exception as e:
                logging.exception(f"Fejl ved stop af testen: {e}")
            return


def monitor_active_calls(
    env: Environment,
    check_interval: float = 5.0,
):
    """
    Tjekker periodisk antallet af aktive opkald og gemmer historikken.
    Skal startes som en greenlet før testen starter.
    """

    # Vent indtil testen kører
    while not env.runner or env.runner.state not in [STATE_RUNNING, STATE_SPAWNING]:
        gevent.sleep(0.5)

    # Initialiser aktive opkald og historik
    env.active_calls = set()
    env.active_calls_history = {}

    while env.runner and env.runner.state in [STATE_RUNNING, STATE_SPAWNING]:
        n_active_calls = len(env.active_calls)
        timestamp = time.time()
        env.active_calls_history[timestamp] = n_active_calls
        gevent.sleep(check_interval)


def save_active_calls_history(
    env: Environment,
    output_file: Path = Path("output/active_calls_history.csv"),
):
    """
    Gemmer historikken over aktive opkald til en CSV-fil.
    Skal kaldes når testen er færdig.
    """
    output_file.parent.mkdir(parents=True, exist_ok=True)

    # Når testen er færdig, gem dataene til en CSV-fil
    try:
        if getattr(env, "active_calls_history", None):
            with output_file.open("w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(["timestamp", "active_calls"])
                for ts, count in env.active_calls_history.items():
                    writer.writerow([ts, count])
            logging.info(f"Gemte aktive opkaldsdata til {output_file}")
        else:
            logging.warning("Ingen aktive opkaldsdata at gemme.")
    except Exception as e:
        logging.exception(f"Fejl ved gemning af aktive opkaldsdata: {e}")
