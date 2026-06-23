from __future__ import annotations

import traceback
from typing import Any

from spark_core.logger.logger import Logger, StubLogger


class ServiceLoggerAdapter(Logger):
    """Lille adapter som giver samme logging-surface som leverance.core."""

    def __init__(self, logger: Logger, request_uid: str | None = None):
        super().__init__(
            log_directory=getattr(logger, "_log_directory", None) or "",
            log_file=getattr(logger, "_log_file", None) or "application.log",
            log_level=getattr(logger, "_log_level", None) or "INFO",
            applikation=getattr(logger, "applikation", None),
            execution_trace_id=getattr(logger, "execution_trace_id", None),
            log_to_console=False,
            log_to_file=False,
        )
        if isinstance(logger, StubLogger):
            self._logs_grouping_key = logger._logs_grouping_key
            self.messages = logger.messages
        else:
            self._log_directory = logger._log_directory
            self._log_file = logger._log_file
            self._log_level = logger._log_level
            self._handlers = logger._handlers

        self.logger = logger.logger
        self.execution_trace_id = logger.execution_trace_id
        self.applikation = logger.applikation
        self.request_uid = request_uid

    @staticmethod
    def _component_name(component: Any) -> str | None:
        if component is None:
            return None
        if hasattr(component, "get_component_name"):
            try:
                return component.get_component_name()
            except TypeError:
                return component.__class__.__name__
        if isinstance(component, str):
            return None
        return component.__class__.__name__

    def service_info(self, component=None, message: str = "", **kwargs: Any):
        if isinstance(component, str) and not message:
            message = component
            component = None
        self.info(
            message,
            component_name=self._component_name(component),
            request_uid=self.request_uid,
            **kwargs,
        )

    def service_warning(self, component=None, message: str = "", **kwargs: Any):
        if isinstance(component, str) and not message:
            message = component
            component = None
        self.warning(
            message,
            component_name=self._component_name(component),
            request_uid=self.request_uid,
            **kwargs,
        )

    def service_exception(self, component=None, message: str = "", **kwargs: Any):
        if isinstance(component, str) and not message:
            message = component
            component = None
        self.exception(
            message,
            component_name=self._component_name(component),
            request_uid=self.request_uid,
            stacktrace=traceback.format_exc(),
            **kwargs,
        )
