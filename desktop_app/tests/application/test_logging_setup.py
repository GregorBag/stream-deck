import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from dj_poltorashka.application.logging_setup import configure_logging


def application_handlers() -> list[RotatingFileHandler]:
    logger = logging.getLogger("dj_poltorashka")
    return [
        handler
        for handler in logger.handlers
        if isinstance(handler, RotatingFileHandler)
    ]


def close_application_handlers() -> None:
    logger = logging.getLogger("dj_poltorashka")
    for handler in tuple(logger.handlers):
        logger.removeHandler(handler)
        handler.close()


def test_configure_logging_creates_rotating_application_log(tmp_path: Path) -> None:
    close_application_handlers()
    logs_dir = tmp_path / "logs"

    log_path = configure_logging(logs_dir)

    handlers = application_handlers()
    assert log_path == logs_dir / "application.log"
    assert log_path.is_file()
    assert len(handlers) == 1
    assert handlers[0].maxBytes == 1024 * 1024
    assert handlers[0].backupCount == 3
    close_application_handlers()


def test_configure_logging_does_not_duplicate_handler(tmp_path: Path) -> None:
    close_application_handlers()

    first_path = configure_logging(tmp_path)
    second_path = configure_logging(tmp_path)

    assert first_path == second_path
    assert len(application_handlers()) == 1
    close_application_handlers()
