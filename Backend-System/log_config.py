import logging
import os
from logging.handlers import RotatingFileHandler


BASE_DIR = os.path.dirname(__file__)
LOG_DIR = os.path.join(BASE_DIR, "logs")
APP_LOG_FILE = os.path.join(LOG_DIR, "app.log")
ERROR_LOG_FILE = os.path.join(LOG_DIR, "error.log")


def configure_logging(app=None):
    os.makedirs(LOG_DIR, exist_ok=True)

    formatter = logging.Formatter(
        "%(asctime)s - %(levelname)s - %(name)s - %(message)s"
    )

    app_handler = RotatingFileHandler(
        APP_LOG_FILE,
        maxBytes=5 * 1024 * 1024,
        backupCount=10,
        encoding="utf-8",
    )
    app_handler.setLevel(logging.INFO)
    app_handler.setFormatter(formatter)

    error_handler = RotatingFileHandler(
        ERROR_LOG_FILE,
        maxBytes=5 * 1024 * 1024,
        backupCount=10,
        encoding="utf-8",
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    existing_files = {
        getattr(handler, "baseFilename", None)
        for handler in root_logger.handlers
    }
    for handler in (app_handler, error_handler):
        if handler.baseFilename not in existing_files:
            root_logger.addHandler(handler)

    if app is not None:
        app.logger.setLevel(logging.INFO)
        for handler in (app_handler, error_handler):
            if all(getattr(item, "baseFilename", None) != handler.baseFilename for item in app.logger.handlers):
                app.logger.addHandler(handler)

    return {
        "log_dir": LOG_DIR,
        "app_log_file": APP_LOG_FILE,
        "error_log_file": ERROR_LOG_FILE,
    }
