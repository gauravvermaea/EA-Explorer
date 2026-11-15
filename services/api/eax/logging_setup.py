"""JSON logs to standard output, one line per event, with the request ID when there is one."""

from __future__ import annotations

import json
import logging
import sys
from datetime import UTC, datetime

from flask import g, has_request_context


class JsonFormatter(logging.Formatter):
    """Writes each log record as one line of JSON: time, level, logger, message, the container and any error."""
    def format(self, record: logging.LogRecord) -> str:
        """One log record as a line of JSON."""
        entry = {
            "time": datetime.now(UTC).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "container": "api",
        }
        if has_request_context():
            entry["request_id"] = getattr(g, "request_id", None)
            entry["user"] = getattr(g, "username", None)
        if record.exc_info:
            entry["error"] = self.formatException(record.exc_info)
        return json.dumps(entry)


def configure_logging(level: str = "INFO") -> None:
    """Sends every log to standard output as JSON lines at the level given (Docker keeps them)."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level)
