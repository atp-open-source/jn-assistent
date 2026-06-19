from __future__ import annotations

import logging
from collections import defaultdict
from pathlib import Path
from typing import Any


class Logger:
    """Let wrapper over stdlib logging med den surface JN bruger."""

    BLACK = "black"
    WHITE = "white"
    BLUE = "blue"
    CYAN = "cyan"
    GREEN = "green"
    MAGENTA = "magenta"
    RED = "red"
    YELLOW = "yellow"

    NORMAL = "normal"
    BOLD = "bold"
    UNDERLINE = "underline"
    ITALIC = "italic"
    STRIKE = "strike"
    DIM = "dim"

    SEP_LINE = "=" * 75

    def __init__(
        self,
        log_directory: str,
        log_file: str = "application.log",
        log_level: str = "INFO",
        applikation: str = "app_logger",
        execution_trace_id: str | None = None,
        log_to_console: bool = True,
        structured_console_log: bool = False,
        log_to_file: bool = True,
        use_queue: bool = False,
    ):
        self.applikation = applikation
        self.execution_trace_id = execution_trace_id
        self._log_directory = str(log_directory)
        self._log_file = log_file
        self._log_level = log_level
        self._log_to_console = log_to_console
        self._structured_console_log = structured_console_log
        self._log_to_file = log_to_file
        self._use_queue = use_queue
        self._handlers: list[logging.Handler] = []

        logger_name = f"{applikation}.{id(self)}"
        self.logger = logging.getLogger(logger_name)
        self.logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))
        self.logger.propagate = False
        self.logger.handlers.clear()

        formatter = logging.Formatter(
            fmt="%(asctime)s [%(levelname)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

        if log_to_console:
            console_handler = logging.StreamHandler()
            console_handler.setFormatter(formatter)
            self.logger.addHandler(console_handler)
            self._handlers.append(console_handler)

        if log_to_file:
            Path(self._log_directory).mkdir(parents=True, exist_ok=True)
            file_handler = logging.FileHandler(Path(self._log_directory) / log_file)
            file_handler.setFormatter(formatter)
            self.logger.addHandler(file_handler)
            self._handlers.append(file_handler)

    def _bind_variables(self, **extra: Any) -> dict[str, Any]:
        bound = {"applikation": self.applikation}
        bound.update({k: v for k, v in extra.items() if v is not None})
        return bound

    @staticmethod
    def _serialize_extra(extra: dict[str, Any]) -> str:
        if not extra:
            return ""
        formatted = ", ".join(f"{key}={value!r}" for key, value in extra.items())
        return f" | {formatted}"

    def print(self, message: str, color: str | None = None, style: str | None = None):
        self.logger.info(str(message))

    def debug(self, message: str, color: str | None = None, style: str | None = None, **extra: Any):
        self.logger.debug(f"{message}{self._serialize_extra(self._bind_variables(**extra))}")

    def info(self, message: str, color: str | None = None, style: str | None = None, **extra: Any):
        self.logger.info(f"{message}{self._serialize_extra(self._bind_variables(**extra))}")

    def warning(self, message: str, color: str | None = None, style: str | None = None, **extra: Any):
        self.logger.warning(f"{message}{self._serialize_extra(self._bind_variables(**extra))}")

    def error(self, message: str, color: str | None = None, style: str | None = None, **extra: Any):
        self.logger.error(f"{message}{self._serialize_extra(self._bind_variables(**extra))}")

    def exception(self, message: str, color: str | None = None, style: str | None = None, **extra: Any):
        self.logger.exception(f"{message}{self._serialize_extra(self._bind_variables(**extra))}")

    def copy(self, **init_kwargs: Any) -> "Logger":
        kwargs = {
            "log_directory": self._log_directory,
            "log_file": self._log_file,
            "log_level": self._log_level,
            "applikation": self.applikation,
            "execution_trace_id": self.execution_trace_id,
            "log_to_console": self._log_to_console,
            "structured_console_log": self._structured_console_log,
            "log_to_file": self._log_to_file,
            "use_queue": self._use_queue,
        }
        kwargs.update(init_kwargs)
        return Logger(**kwargs)

    def remove_handlers(self):
        for handler in list(self._handlers):
            self.logger.removeHandler(handler)
            handler.close()
        self._handlers.clear()

    def await_queued_messages(self):
        return None


class StubLogger(Logger):
    """Logger-variant der opsamler beskeder i hukommelsen."""

    def __init__(self, applikation: str = "default_app", group_logs_by: str = "event_name"):
        self.applikation = applikation
        self.execution_trace_id = None
        self._log_directory = ""
        self._log_file = ""
        self._log_level = "INFO"
        self._handlers = []
        self._logs_grouping_key = group_logs_by
        self.messages: dict[str, list[dict[str, Any]]] = defaultdict(list)
        self.logger = logging.getLogger(f"stub.{applikation}.{id(self)}")
        self.logger.handlers.clear()
        self.logger.propagate = False
        self.logger.setLevel(logging.INFO)

    def _store(self, level: str, message: str, **extra: Any):
        payload = {"message": str(message), **self._bind_variables(**extra)}
        key = payload.get(self._logs_grouping_key, level)
        self.messages[key].append(payload)
        self.messages[level].append(payload)

    def debug(self, message: str, color: str | None = None, style: str | None = None, **extra: Any):
        self._store("debug", message, **extra)

    def info(self, message: str, color: str | None = None, style: str | None = None, **extra: Any):
        self._store("info", message, **extra)

    def warning(self, message: str, color: str | None = None, style: str | None = None, **extra: Any):
        self._store("warning", message, **extra)

    def error(self, message: str, color: str | None = None, style: str | None = None, **extra: Any):
        self._store("error", message, **extra)

    def exception(self, message: str, color: str | None = None, style: str | None = None, **extra: Any):
        self._store("exception", message, **extra)
