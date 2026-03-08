"""Unit tests for shared logging setup."""

import logging

from vocal_core.logging import get_logger, setup_logging


def test_get_logger_returns_logger():
    logger = get_logger("vocal_core.test")
    assert isinstance(logger, logging.Logger)
    assert logger.name == "vocal_core.test"


def test_setup_logging_sets_level():
    setup_logging(level="DEBUG")
    root = logging.getLogger()
    assert root.level == logging.DEBUG


def test_setup_logging_invalid_level_falls_back():
    setup_logging(level="NOTREAL")
    root = logging.getLogger()
    assert root.level == logging.INFO


def test_setup_logging_custom_format():
    setup_logging(level="WARNING", fmt="%(levelname)s %(message)s")
    root = logging.getLogger()
    assert root.level == logging.WARNING
