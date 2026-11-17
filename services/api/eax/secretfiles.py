"""The passwords and keys as files of their own (R6-F1, D745).

Docker gives each container only the secrets it needs, as files under /run/secrets named as their settings
(docker-compose.yml's secrets), never as environment variables, so docker inspect and the container's settings show
none. This reads them into this process's own environment once, when the eax package is first imported, so the code
that reads a setting (eax/config.py and the rest) finds it as before. A value already in the environment is kept
(tests, or a setting given on purpose); an empty file is skipped."""

from __future__ import annotations

import os
import re
from pathlib import Path

FOLDER = Path(os.environ.get("EAX_SECRETS_DIR", "/run/secrets"))
NAME = re.compile(r"^EAX_[A-Z0-9_]+$")


def load(folder: Path = FOLDER, environ: dict | None = None) -> list[str]:
    """Each EAX_* file in the folder into the environment, unless it is set already; the names read (never values)."""
    env = os.environ if environ is None else environ
    read = []
    try:
        files = sorted(p for p in folder.iterdir() if p.is_file() and NAME.match(p.name))
    except OSError:
        return read
    for p in files:
        try:
            value = p.read_text(encoding="utf-8").strip("\r\n")
        except OSError:
            continue
        if value and not env.get(p.name):
            env[p.name] = value
            read.append(p.name)
    return read
