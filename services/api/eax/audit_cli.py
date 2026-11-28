"""One line in the audit log from the eax command on the machine (D975): python -m eax.audit_cli <action> <who> [detail].
Used by eax logins, which shows the passwords on the screen only: who looked, and when, is kept here (the values never)."""

from __future__ import annotations

import sys

from . import audit
from .db import get_engine


def main(argv: list[str]) -> int:
    """Records the action; 2 when it is not given."""
    if len(argv) < 2:
        print("Usage: python -m eax.audit_cli <action> <who> [detail]")
        return 2
    with get_engine().begin() as conn:
        audit.record(conn, actor=argv[1][:120], action=argv[0][:80], object_type="installation",
                     details={"detail": " ".join(argv[2:])[:300]}, source="eax")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
