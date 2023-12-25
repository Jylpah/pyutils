import logging
import sys
from typing import Literal, Optional
from pathlib import Path


def set_mlevel_logging(
    logger: logging.Logger,
    fmts: Optional[dict[int, str]] = None,
    fmt: Optional[str] = None,
    datefmt: Optional[str] = None,
    style: Literal["%", "{", "$"] = "%",
    validate: bool = True,
    log_file: Optional[str | Path] = None,
):
    """Setup logging"""
    if fmts is not None:
        multi_formatter = MultilevelFormatter(
            fmt=fmt, fmts=fmts, datefmt=datefmt, style=style, validate=validate
        )
        stream_handler = logging.StreamHandler(sys.stdout)
        stream_handler.setFormatter(multi_formatter)
        logger.addHandler(stream_handler)

    if log_file is not None:
        file_handler = logging.FileHandler(log_file)
        log_formatter = logging.Formatter(fmt=fmt, style=style, validate=validate)
        file_handler.setFormatter(log_formatter)
        logger.addHandler(file_handler)


class MultilevelFormatter(logging.Formatter):
    """
    logging.Formatter that simplifies setting different log formats for different log levels
    """

    _levels: list[int] = [
        logging.NOTSET,
        logging.DEBUG,
        logging.INFO,
        logging.WARNING,
        logging.ERROR,
        logging.CRITICAL,
    ]

    def __init__(
        self,
        fmts: dict[int, str],
        fmt: Optional[str] = None,
        datefmt: Optional[str] = None,
        style: Literal["%", "{", "$"] = "%",
        validate: bool = True,
        *,
        defaults=None,
    ):
        assert fmts is not None, "styles cannot be None"

        self._formatters: dict[int, logging.Formatter] = dict()
        for level in self._levels:
            self._formatters[level] = logging.Formatter(
                fmt=fmt,
                datefmt=datefmt,
                style=style,
                validate=validate,
                defaults=defaults,
            )

        for level in fmts.keys():
            self._formatters[level] = logging.Formatter(fmt=fmts[level], style=style)

    @classmethod
    def setLevels(
        cls,
        logger: logging.Logger,
        fmts: Optional[dict[int, str]] = None,
        fmt: Optional[str] = None,
        datefmt: Optional[str] = None,
        style: Literal["%", "{", "$"] = "%",
        validate: bool = True,
        log_file: Optional[str | Path] = None,
    ) -> None:
        """Setup logging"""
        if fmts is not None:
            multi_formatter = MultilevelFormatter(
                fmt=fmt, fmts=fmts, datefmt=datefmt, style=style, validate=validate
            )
            stream_handler = logging.StreamHandler(sys.stdout)
            stream_handler.setFormatter(multi_formatter)
            logger.addHandler(stream_handler)

        if log_file is not None:
            file_handler = logging.FileHandler(log_file)
            log_formatter = logging.Formatter(fmt=fmt, style=style, validate=validate)
            file_handler.setFormatter(log_formatter)
            logger.addHandler(file_handler)

    @classmethod
    def setDefaults(
        cls, logger: logging.Logger, log_file: Optional[str | Path] = None
    ) -> None:
        """Set multi-level formatting defaults

        INFO: %(message)s
        WARNING: %(message)s
        Others: %(levelname)s: %(funcName)s(): %(message)s

        """
        logger_conf: dict[int, str] = {
            logging.INFO: "%(message)s",
            logging.WARNING: "%(message)s",
            # logging.ERROR: 		'%(levelname)s: %(message)s'
        }
        MultilevelFormatter.setLevels(
            logger,
            fmts=logger_conf,
            fmt="%(levelname)s: %(funcName)s(): %(message)s",
            log_file=log_file,
        )

    def format(self, record: logging.LogRecord) -> str:
        try:
            return self._formatters[record.levelno].format(record)
        except Exception as err:
            logging.error(f"{err}")
            return f"{err}"

    def formatTime(self, record: logging.LogRecord, datefmt: Optional[str] = None):
        try:
            return self._formatters[record.levelno].formatTime(
                record=record, datefmt=datefmt
            )
        except Exception as err:
            logging.error(f"{err}")
            return f"{err}"
