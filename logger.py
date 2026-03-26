"""
Logger Utility
---------------
Centralized logging configuration.
All modules use this to get a consistent logger.
"""

import logging
import sys
import os


def get_logger(name: str) -> logging.Logger:
    """
    Get a configured logger for the given module name.
    
    Log level is controlled by the LOG_LEVEL environment variable.
    Defaults to INFO.
    """
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()

    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, log_level, logging.INFO))

    # Avoid adding duplicate handlers in hot-reload scenarios
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(getattr(logging, log_level, logging.INFO))

        formatter = logging.Formatter(
            fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    return logger
