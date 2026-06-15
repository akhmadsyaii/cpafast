import logging
import os
from logging.handlers import RotatingFileHandler
from typing import Optional


class BotLogger:
    _instance: Optional["BotLogger"] = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, config=None):
        if hasattr(self, "_initialized") and self._initialized:
            return
        self._initialized = True
        self.config = config
        self.logger: Optional[logging.Logger] = None
        if config:
            self.setup(config)

    def setup(self, config):
        self.config = config
        self.logger = logging.getLogger("CPABot")
        self.logger.setLevel(getattr(logging, config.log_level.upper(), logging.INFO))

        # Remove existing handlers to prevent duplicates on re-setup
        self.logger.handlers.clear()

        log_dir = os.path.dirname(config.log_file)
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)

        file_handler = RotatingFileHandler(
            config.log_file,
            maxBytes=config.log_max_size * 1024 * 1024,
            backupCount=config.log_backup_count,
        )
        file_handler.setFormatter(logging.Formatter(
            "%(asctime)s [%(levelname)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        ))
        self.logger.addHandler(file_handler)

        if config.get("logging", "console_output", default=True):
            console = logging.StreamHandler()
            console.setFormatter(logging.Formatter(
                "%(asctime)s [%(levelname)s] %(message)s",
                datefmt="%H:%M:%S",
            ))
            self.logger.addHandler(console)

        self.logger.propagate = False

    def info(self, msg: str):
        if self.logger:
            self.logger.info(msg)

    def warn(self, msg: str):
        if self.logger:
            self.logger.warning(msg)

    def error(self, msg: str):
        if self.logger:
            self.logger.error(msg)

    def debug(self, msg: str):
        if self.logger:
            self.logger.debug(msg)

    def success(self, msg: str):
        if self.logger:
            self.logger.info(f"[SUCCESS] {msg}")

    def fail(self, msg: str):
        if self.logger:
            self.logger.warning(f"[FAIL] {msg}")


logger = BotLogger()
