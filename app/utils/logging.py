"""Structured logging configuration with sensitive data masking and UTF-8 console output."""

import io
import logging
import sys
from typing import Any
from app.config import config


class SensitiveDataFilter(logging.Filter):
    """Filter to ensure bot tokens and credentials are never leaked in logs."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            token = config.BOT_TOKEN
            if token and len(token) > 10 and token in record.msg:
                record.msg = record.msg.replace(token, config.masked_token())
            if isinstance(record.args, tuple):
                cleaned_args = []
                for arg in record.args:
                    if isinstance(arg, str) and token and token in arg:
                        cleaned_args.append(arg.replace(token, config.masked_token()))
                    else:
                        cleaned_args.append(arg)
                record.args = tuple(cleaned_args)
            elif isinstance(record.args, dict):
                cleaned_dict = {}
                for k, v in record.args.items():
                    if isinstance(v, str) and token and token in v:
                        cleaned_dict[k] = v.replace(token, config.masked_token())
                    else:
                        cleaned_dict[k] = v
                record.args = cleaned_dict
        return True


def setup_logger(name: str = "telegram_manager") -> logging.Logger:
    """Set up and return a structured console logger with UTF-8 safe stream."""
    logger = logging.getLogger(name)

    log_level = getattr(logging, config.LOG_LEVEL, logging.INFO)
    logger.setLevel(log_level)

    # Avoid duplicate handlers if already configured
    if not logger.handlers:
        # Wrap sys.stdout in a UTF-8 stream writer with error replacement on Windows
        try:
            if hasattr(sys.stdout, "buffer"):
                utf8_stdout = io.TextIOWrapper(
                    sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True
                )
            else:
                utf8_stdout = sys.stdout
        except Exception:
            utf8_stdout = sys.stdout

        handler = logging.StreamHandler(utf8_stdout)
        handler.setLevel(log_level)
        formatter = logging.Formatter(
            fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        handler.addFilter(SensitiveDataFilter())
        logger.addHandler(handler)

    # Suppress verbose HTTP logs from httpx and urllib3 unless in DEBUG
    if log_level > logging.DEBUG:
        logging.getLogger("httpx").setLevel(logging.WARNING)
        logging.getLogger("httpcore").setLevel(logging.WARNING)
        logging.getLogger("telegram").setLevel(logging.INFO)

    return logger


logger = setup_logger()
