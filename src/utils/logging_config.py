import logging
from pathlib import Path

def configure_logging() -> logging.Logger:
    # File content, message bodies, customer data, and paths are intentionally not logged.
    logger = logging.getLogger("father_automation")
    if not logger.handlers:
        logger.setLevel(logging.WARNING)
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
        logger.addHandler(handler)
    return logger
