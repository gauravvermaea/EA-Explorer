"""The error guide (Release 7.9, D787), written from the one list of error codes, services/api/eax/errors.json, to
docs/site/guides/error-codes.md: the website shows it among the Guides and the printed Troubleshooting guide (21)
includes it. `eax site build` writes it again each time, so it never differs from the list; a test checks the two
agree. Standard library only.

    python tools/error_guide.py           write the page
    python tools/error_guide.py --check   say whether the page is out of step (exit 1 when it is)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LIST = ROOT / "services" / "api" / "eax" / "errors.json"
PAGE = ROOT / "docs" / "site" / "guides" / "error-codes.md"

# each area's heading, in the order the guide gives them
AREAS = [
    ("STACK", "Docker and the containers"), ("API", "The API's answers"), ("PART", "Parts switched off"),
    ("MNT", "Maintenance"), ("DR", "Disaster recovery"), ("DB", "The database"), ("JOB", "Background jobs"),
    ("AUTH", "Sign-in"), ("BRK", "The break-glass account"), ("WEB", "The web screens"), ("PROXY", "The front door"),
    ("RPT", "Reports"), ("DOC", "Documents"), ("DRAW", "Diagrams"), ("LIB", "The library"), ("VIEW", "Drawn views"),
    ("OPS", "Operations"), ("PDATA", "Personal data"), ("MCP", "The MCP server"), ("BAK", "Backups"),
    ("DISK", "Disk space"), ("MEM", "Memory"), ("CERT", "Certificates"), ("SEC", "Secrets and security"),
    ("TEST", "Self-tests"), ("ALRT", "Alerts"),
]

INTRO = """---
title: Error codes
summary: Every error code EA Explorer gives, what it means, its usual cause and what to do.
group: Running it
roles: system-admin
---

## Why do this

When something goes wrong, EA Explorer says so with a code of the form `EAX-AREA-NNN`, for example `EAX-AUTH-001`. The
area says which part it is about; the number tells problems in one area apart. A code never changes its meaning, so you
can look it up here, search the logs for it and quote it when you ask for help. See [[running-the-installation]].

**In TOGAF terms:** Outside the method: this keeps the tool that holds the Architecture Repository running. See [[ea-explorer-and-togaf]].

**The goal:** For any problem, you know what it means and what to do next.

> **Before you start** Anyone can read this guide; most of what it asks you to do needs the Super Admin or IT Admin role,
> or the machine EA Explorer runs on.

## Where you see the codes

- **`eax status`** on the machine: after the containers and the disks, every problem now with its code and what to do.
  `eax status problems` lists the problems only; `eax errors <code>` explains one code.
- **System Admin › Running › Health**: each part that is not up shows its code and what to do.
- **System Admin › Running › Alerts**: each open alert shows its code and what to do; its notification and email name
  the code too.
- **The screens**: an error message ends with its code in brackets.
- **The API**: every error answer has `error_code` and `to_do` beside `message`, and the header `X-EAX-Error-Code`.
- **The logs**: the API's log lines about a problem carry `error_code`, so `eax logs api` and System Admin › Running ›
  Logs can be searched by code.

When the code is `EAX-API-500`, the message also gives a request id: `eax logs api` shows what happened under that id;
give the id when you report the problem.

## Each task, one page

1. [Find what an error code means](../how-do-i/find-what-an-error-code-means.md)
2. [See every problem from the machine](../how-do-i/see-every-problem-from-the-machine.md)
3. [See the health of every part](../how-do-i/see-the-health-of-every-part.md)
4. [Read the logs](../how-do-i/read-the-logs.md)

## The codes

Each area below lists its codes in order. Do what a code says, in order; if the problem stays, `eax diag` saves a
report to send with the code.
"""


def errors() -> list[dict]:
    """Every code in the list."""
    return json.loads(LIST.read_text(encoding="utf-8"))["errors"]


def page() -> str:
    """The guide's Markdown, from the list."""
    out = [INTRO]
    items = errors()
    named = {a for a, _ in AREAS}
    areas = AREAS + [(a, a) for a in dict.fromkeys(e["area"] for e in items) if a not in named]
    for area, heading in areas:
        mine = sorted((e for e in items if e["area"] == area), key=lambda e: e["code"])
        if not mine:
            continue
        out.append(f"### {heading} ({area})\n")
        for e in mine:
            out.append(f"**{e['code']}: {e['title']}.** {e['meaning']}\n\n"
                       f"Usual cause: {e['cause']}\n\n"
                       f"What to do: {e['to_do']}\n")
    return "\n".join(out).rstrip() + "\n"


def main(argv: list[str]) -> int:
    text = page()
    if "--check" in argv:
        same = PAGE.is_file() and PAGE.read_text(encoding="utf-8") == text
        print("The error guide agrees with the list." if same else f"{PAGE} is out of step: run python tools/error_guide.py")
        return 0 if same else 1
    PAGE.write_text(text, encoding="utf-8", newline="\n")
    print(f"Wrote {PAGE.relative_to(ROOT)} ({len(errors())} codes).")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
