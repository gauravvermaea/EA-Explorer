"""eax optimise (R5.1, D697): the optimisation report from the command line, the same as System Admin > Optimisation.
It runs eax/optimise.py in the api container. Nothing is changed here: each suggestion is applied on the screen, for a
whole model or project, by the person who decides it.

  eax optimise          measure now, keep the report and print it
  eax optimise last     print the newest report (the monthly one, or the last measured)
"""

from __future__ import annotations

import sys

from .core import Failure, attached, compose_args

COMMANDS = ("report", "last")


def main(rest: list[str]) -> int:
    """eax optimise: the optimisation report in the api container."""
    args = rest or ["report"]
    if args[0] not in COMMANDS:
        raise Failure("eax optimise [report|last]")
    tty = [] if sys.stdin.isatty() else ["-T"]
    return attached(compose_args(["exec", *tty, "api", "python", "-m", "eax.optimise", *args]))
