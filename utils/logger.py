import logging
import os
import sys
from typing import Optional
from contextvars import ContextVar


# Context variable for request/correlation ID
request_id_context: ContextVar[Optional[str]] = ContextVar('request_id', default=None)

class Logger:
    def __init__(
        self,
        name: str = "AppLogger",
        level: str = "INFO",
        log_to_file: bool = False,
        log_file_path: Optional[str] = "app.log",
    ):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(self._get_log_level(level))
        self.logger.propagate = False  # Prevent double logging

        formatter = logging.Formatter(
            fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

        # Stream handler (console)
        stream_handler = logging.StreamHandler(sys.stdout)
        stream_handler.setFormatter(formatter)
        self.logger.addHandler(stream_handler)

        # Optional file handler
        if log_to_file and log_file_path:
            file_handler = logging.FileHandler(log_file_path)
            file_handler.setFormatter(formatter)
            self.logger.addHandler(file_handler)

    def _get_log_level(self, level_str: str) -> int:
        return {
            "DEBUG": logging.DEBUG,
            "INFO": logging.INFO,
            "WARNING": logging.WARNING,
            "ERROR": logging.ERROR,
            "CRITICAL": logging.CRITICAL,
        }.get(level_str.upper(), logging.INFO)

    def debug(self, msg: str, *args, **kwargs):
        self.logger.debug(msg, *args, **kwargs)

    def info(self, msg: str, *args, **kwargs):
        self.logger.info(msg, *args, **kwargs)

    def warning(self, msg: str, *args, **kwargs):
        self.logger.warning(msg, *args, **kwargs)

    def error(self, msg: str, *args, **kwargs):
        self.logger.error(msg, *args, **kwargs)

    def critical(self, msg: str, *args, **kwargs):
        self.logger.critical(msg, *args, **kwargs)

    def log(self, level, msg, *args, **kwargs):
        self.logger.log(level, msg, *args, **kwargs)
    
    def set_request_id(self, request_id: str):
        """Set the request/correlation ID for this context."""
        request_id_context.set(request_id)
    
    def get_request_id(self) -> Optional[str]:
        """Get the current request/correlation ID."""
        return request_id_context.get()
    
    def close(self):
        """Close all handlers"""
        for handler in self.logger.handlers[:]:
            handler.close()
            self.logger.removeHandler(handler)
