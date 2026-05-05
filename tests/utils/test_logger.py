import logging
from crypto_research_agent.utils.logger import get_logger


def test_get_logger_returns_logger():
    logger = get_logger("test_module_new")
    assert isinstance(logger, logging.Logger)
    assert logger.name == "test_module_new"


def test_get_logger_idempotent():
    a = get_logger("dup")
    b = get_logger("dup")
    assert a is b
    root = logging.getLogger()
    assert len(root.handlers) > 0
