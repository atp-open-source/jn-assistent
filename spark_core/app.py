from __future__ import annotations

from spark_core.config.base_config import Config, get_project_config
from spark_core.logger.logger import Logger


class App:
    """Samler shim-konfiguration og logger."""

    def __init__(
        self,
        config: Config | None = None,
        applikation: str = "default_app",
        use_db_server: str = "default",
        use_db_group: str = "default",
    ):
        self.config = config or get_project_config()
        self.name = applikation
        self.use_db_server = use_db_server
        self.use_db_group = use_db_group
        self.db_server_name = use_db_server
        self.db_server_group_name = use_db_group
        self.log = Logger(
            log_directory=self.config.LOGS_PATH,
            log_file=f"{applikation.lower()}.log",
            log_level=self.config.LOG_LEVEL,
            applikation=applikation,
            log_to_file=getattr(self.config, "LOG_TO_FILE", False),
        )
        self.selfishly = False
