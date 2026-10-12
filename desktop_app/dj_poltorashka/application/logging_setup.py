"""Настройка файлового журнала приложения."""

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path


_LOGGER_NAME = "dj_poltorashka"
_HANDLER_NAME = "dj_poltorashka_file"


def configure_logging(logs_dir: Path) -> Path:
    """Настроить единственный ротируемый обработчик и вернуть путь журнала."""
    directory = Path(logs_dir)
    directory.mkdir(parents=True, exist_ok=True)
    log_path = directory / "application.log"
    expected_path = log_path.resolve()
    logger = logging.getLogger(_LOGGER_NAME)

    for handler in tuple(logger.handlers):
        if handler.get_name() != _HANDLER_NAME:
            continue
        if (
            isinstance(handler, RotatingFileHandler)
            and Path(handler.baseFilename) == expected_path
        ):
            return log_path
        logger.removeHandler(handler)
        handler.close()

    handler = RotatingFileHandler(
        log_path,
        maxBytes=1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    handler.set_name(_HANDLER_NAME)
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s %(levelname)s %(name)s: %(message)s",
        )
    )
    logger.setLevel(logging.INFO)
    logger.propagate = False
    logger.addHandler(handler)
    return log_path
