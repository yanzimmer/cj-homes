import logging
import os
import re
from logging.handlers import TimedRotatingFileHandler


BASE_DIR = os.path.dirname(__file__)
LOG_DIR = os.path.join(BASE_DIR, "logs")
APP_LOG_FILE = os.path.join(LOG_DIR, "app.log")
ERROR_LOG_FILE = os.path.join(LOG_DIR, "error.log")


def _file_handler_path(handler):
    return getattr(handler, "baseFilename", None)


def _remove_file_handlers(logger, file_paths, close=False):
    for handler in list(logger.handlers):
        if _file_handler_path(handler) in file_paths:
            logger.removeHandler(handler)
            if close:
                try:
                    handler.close()
                except Exception:
                    pass


def _add_handler_once(logger, handler):
    existing_files = {
        _file_handler_path(item)
        for item in logger.handlers
    }
    if handler.baseFilename in existing_files:
        handler.close()
        return
    logger.addHandler(handler)


def configure_logging(app=None):
    os.makedirs(LOG_DIR, exist_ok=True)
    log_files = {APP_LOG_FILE, ERROR_LOG_FILE}

    if app is not None:
        _remove_file_handlers(app.logger, log_files)
        app.logger.setLevel(logging.INFO)
        app.logger.propagate = True

    formatter = logging.Formatter(
        "%(asctime)s - %(levelname)s - %(name)s - %(message)s"
    )

    app_handler = TimedRotatingFileHandler(
        APP_LOG_FILE,
        when="midnight",
        interval=1,
        backupCount=30,
        encoding="utf-8",
    )
    app_handler.suffix = "%Y%m%d"
    app_handler.extMatch = re.compile(r"^\d{8}$")
    app_handler.setLevel(logging.INFO)
    app_handler.setFormatter(formatter)

    error_handler = TimedRotatingFileHandler(
        ERROR_LOG_FILE,
        when="midnight",
        interval=1,
        backupCount=30,
        encoding="utf-8",
    )
    error_handler.suffix = "%Y%m%d"
    error_handler.extMatch = re.compile(r"^\d{8}$")
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    for handler in (app_handler, error_handler):
        _add_handler_once(root_logger, handler)

    return {
        "log_dir": LOG_DIR,
        "app_log_file": APP_LOG_FILE,
        "error_log_file": ERROR_LOG_FILE,
    }
