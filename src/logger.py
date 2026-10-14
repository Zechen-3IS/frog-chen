import logging
import os
from datetime import date

LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

_initialized = False


def _ensure_root_handlers():
    """Attach file + console handlers to the root logger exactly once."""
    global _initialized
    if _initialized:
        return
    _initialized = True

    os.makedirs(LOG_DIR, exist_ok=True)

    formatter = logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT)

    # Daily log file
    file_handler = logging.FileHandler(
        os.path.join(LOG_DIR, f"{date.today().isoformat()}.log"),
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)

    # Console
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(file_handler)
    root.addHandler(console_handler)


def get_logger(name: str) -> logging.Logger:
    """Return a named logger, initialising root handlers on first call."""
    _ensure_root_handlers()
    return logging.getLogger(name)
