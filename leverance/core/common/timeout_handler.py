import queue
import threading

from spark_core.logger.logger import Logger


class TimeoutException(Exception):  # noqa: N818 - navn matcher leverance.core-framework'et
    """Custom exception til at indikere timeout"""

    def __init__(self, message, timeout_duration):
        super().__init__(message)
        self.timeout_duration = timeout_duration
        self.is_timeout = True


def run_with_timeout(
    timeout, result_by_timeout, log_besked=None, log_type=None, raise_on_timeout=False
):
    """
    Funktion der håndterer timeout på en funktion, således at funktionen afbrydes
    efter et givent antal sekunder (timeout), og returnerer en specificeret værdi
    i stedet for (result_by_timeout).
    Herudover er det muligt at give en besked der skal logges, hvis timeout
    indtræffer (log_besked), af den type log der defineres (log_type).

    Args:
        timeout: Antal sekunder før timeout indtræffer
        result_by_timeout: Værdi der returneres ved timeout (hvis raise_on_timeout=False)
        log_besked: Besked der logges ved timeout
        log_type: Type af logbesked (info, warning, error, osv.)
        raise_on_timeout: Hvis True, kastes TimeoutException i stedet for at returnere result_by_timeout
    """

    def decorator(func):
        def wrapper(*args, **kwargs):
            result_queue = queue.Queue()
            exception_queue = queue.Queue()

            def target():
                try:
                    result_queue.put(func(*args, **kwargs))
                except Exception as e:
                    exception_queue.put(e)

            thread = threading.Thread(target=target)
            thread.daemon = True
            thread.start()
            thread.join(timeout)

            if thread.is_alive():
                if log_besked:
                    print("Logging timeout besked - søg her")
                    if not hasattr(Logger, log_type):
                        raise ValueError(f"Der findes ingen log metode af typen: '{log_type}'")
                    logger = args[0].app.log
                    log_method = getattr(Logger, log_type)
                    log_method(logger, log_besked)

                # raise hvis ønsket
                if raise_on_timeout:
                    raise TimeoutException(
                        f"Function {func.__name__} timed out after {timeout} seconds",
                        timeout,
                    )

                return result_by_timeout
            else:
                if not exception_queue.empty():
                    raise exception_queue.get()

                result = result_queue.get()
                return result

        return wrapper

    return decorator
