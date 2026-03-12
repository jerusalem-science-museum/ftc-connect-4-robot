import platform
from pathlib import Path

import yaml
import serial.tools.list_ports

from connect4_engine.utils.logger import logger

def resolve_port(label: str) -> str | None:
    """Pick the right port for the current OS. If it's a list, probe until one exists."""
    _config = None
    with Path("config.yaml").open("r", encoding="utf-8") as _f:
        _config = yaml.safe_load(_f)
    device_cfg = _config["hardware"][label]
    key = "portwin" if platform.system() == "Windows" else "portlinux"
    port = device_cfg.get(key)

    if port is None:
        return None

    if not isinstance(port, list):
        logger.info("Using %s for %s", port, label)
        return port

    available = {p.device for p in serial.tools.list_ports.comports()}
    for candidate in port:
        if candidate in available:
            logger.info("Using %s for %s", candidate, label)
            return candidate

    logger.warning("None of %s found for %s", port, label)
    return None

