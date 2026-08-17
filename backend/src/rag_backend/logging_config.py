"""Centralised logging setup.

Library modules must only call ``logging.getLogger(__name__)``. Handler and
level configuration happens once, here, at application startup.
"""

from __future__ import annotations

import logging

LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"


def configure_logging(level: str = "INFO") -> None:
    """Configure root logging for the process."""
    logging.basicConfig(level=level.upper(), format=LOG_FORMAT, force=True)
