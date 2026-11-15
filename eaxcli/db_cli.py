"""eax db (R5.12, D691): database maintenance from the command line, the same as System Admin > Database maintenance.
It runs eax/dbmaint.py in the api container:

  eax db check                        every database checked now: what needs doing, in plain words
  eax db tidy [--dry-run]             what the check finds, done (VACUUM, ANALYZE, REINDEX CONCURRENTLY; nothing locked)
  eax db compact <database> <table>   VACUUM FULL of one table (it locks the table): the space it wins said first
  eax db clear                        the keep-for rules applied now (housekeeping, old alert history)
  eax db locks                        who blocks whom
  eax db cancel <pid> | end <pid>     cancel a session's query, or end the session (asked first)
"""

from __future__ import annotations

import sys

from .core import Failure, attached, compose_args

COMMANDS = ("check", "tidy", "compact", "clear", "locks", "cancel", "end")


def main(rest: list[str]) -> int:
    """eax db: database maintenance in the api container."""
    args = rest or ["check"]
    if args[0] not in COMMANDS:
        raise Failure("eax db check | tidy [--dry-run] | compact <database> <table> | clear | locks | cancel <pid> | end <pid>")
    tty = [] if sys.stdin.isatty() else ["-T"]
    return attached(compose_args(["exec", *tty, "api", "python", "-m", "eax.dbmaint", *args]))
