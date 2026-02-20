# tests/utils/test_logger.py
import logging
import sys
sys.path.insert(0, '.')
from utils.logger import get_logger

def test_get_logger_returns_logger():
    logger = get_logger("test_module")
    assert isinstance(logger, logging.Logger)
    assert logger.name == "test_module"

def test_get_logger_has_handlers():
    get_logger("test_handlers")
    root = logging.getLogger()
    assert len(root.handlers) > 0
