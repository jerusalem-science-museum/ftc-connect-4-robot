import logging
import sys
from enum import Enum, auto
from pathlib import Path
import yaml
import time
import functools

class OutputTarget(Enum):
    FILE = auto()
    STDOUT = auto()
    BOTH = auto()


def _load_logging_config(path: str = "config.yaml") -> dict:
    cfg_path = Path(path)
    with cfg_path.open("r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    return config.get("logging", {})


def _parse_level(level_name: str) -> int:
    # Map string (DEBUG, INFO, etc.) to logging level
    return getattr(logging, level_name.upper(), logging.INFO)

def setup_logger(name: str = "game") -> logging.Logger:
    log_cfg = _load_logging_config()

    level = _parse_level(log_cfg.get("level", "INFO"))
    output_str = log_cfg.get("output", "BOTH").upper()
    logfile = log_cfg.get("logfile", "game.log")
    overwrite = bool(log_cfg.get("overwrite", False))

    if output_str == "FILE":
        output = OutputTarget.FILE
    elif output_str == "STDOUT":
        output = OutputTarget.STDOUT
    else:
        output = OutputTarget.BOTH

    logger = logging.getLogger(name)
    logger.setLevel(level)

    if logger.handlers:
        return logger

    fmt = "%(asctime)s - %(levelname)s - %(funcName)s() - %(message)s"
    datefmt = "%Y-%m-%d %H:%M:%S"
    formatter = logging.Formatter(fmt=fmt, datefmt=datefmt)

    file_mode = "w" if overwrite else "a"

    if output in (OutputTarget.FILE, OutputTarget.BOTH):
        file_handler = logging.FileHandler(logfile, mode=file_mode, encoding="utf-8")
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    if output in (OutputTarget.STDOUT, OutputTarget.BOTH):
        stream_handler = logging.StreamHandler(sys.stdout)
        stream_handler.setFormatter(formatter)
        logger.addHandler(stream_handler)

    return logger


def timed(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        t0 = time.perf_counter()
        result = func(*args, **kwargs)
        print(f"[TIMER] {func.__name__}: {time.perf_counter() - t0:.3f}s")
        return result
    return wrapper


# Default logger you can import directly
logger = setup_logger()
