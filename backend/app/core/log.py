from __future__ import annotations

import json
import logging
import shlex
from collections.abc import Mapping

_REDACT_HEADERS = {"authorization", "x-api-key", "api-key", "cookie"}


class AppLogger:
    """Pass this into clients/services. Use child() for a named subsystem."""

    def __init__(self, logger: logging.Logger) -> None:
        self._log = logger

    def child(self, name: str) -> AppLogger:
        return AppLogger(self._log.getChild(name))

    def debug(self, msg: str, *args: object) -> None:
        self._log.debug(msg, *args)

    def info(self, msg: str, *args: object) -> None:
        self._log.info(msg, *args)

    def warning(self, msg: str, *args: object) -> None:
        self._log.warning(msg, *args)

    def error(self, msg: str, *args: object) -> None:
        self._log.error(msg, *args)

    def exception(self, msg: str, *args: object) -> None:
        self._log.exception(msg, *args)

    def curl(
        self,
        method: str,
        url: str,
        headers: Mapping[str, str],
        body: object | None = None,
    ) -> None:
        self._log.info("\n%s", format_curl(method, url, headers, body))


def configure_logging(level: str = "DEBUG") -> AppLogger:
    root = logging.getLogger("chatkb")
    numeric = getattr(logging, level.upper(), logging.DEBUG)
    root.setLevel(numeric)
    root.propagate = False
    if not root.handlers:
        handler = logging.StreamHandler()
        handler.setLevel(numeric)
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s %(levelname)s [%(name)s] %(message)s",
                datefmt="%H:%M:%S",
            )
        )
        root.addHandler(handler)
    else:
        for existing in root.handlers:
            existing.setLevel(numeric)
    return AppLogger(root)


def get_logger(name: str = "chatkb") -> AppLogger:
    return AppLogger(logging.getLogger(name))


def format_curl(
    method: str,
    url: str,
    headers: Mapping[str, str],
    body: object | None = None,
) -> str:
    parts = [f"curl -sS -X {method.upper()} {shlex.quote(url)}"]
    for key, value in headers.items():
        shown = "***" if key.lower() in _REDACT_HEADERS else value
        parts.append(f"  -H {shlex.quote(f'{key}: {shown}')}")
    if body is not None:
        if isinstance(body, str):
            payload = body
        else:
            payload = json.dumps(body, ensure_ascii=False, indent=2)
        parts.append(f"  -d {shlex.quote(payload)}")
    return " \\\n".join(parts)
