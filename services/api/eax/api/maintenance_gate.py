"""Anything that puts the maintenance page up asks first (the owner, 18 Nov 2026, 10:32: "Anything that will bring up
mantaiance page needs to show a warning and user to accept it"; after "Check the integrity now" put it up unasked).

Every API call that puts the maintenance page up, now or later on a schedule, is refused with 428 until the request says
accept_maintenance: true. The screens' apiFetch shows the warning, and on OK sends the same request again with the yes;
so every screen, today's and tomorrow's, asks the same way. The command line and Jenkins are not asked: a person typed
the command, or typed the installation's name.
"""

from __future__ import annotations

from flask_smorest import abort

NOW = "the maintenance page goes up for everyone, the background is let finish first, and EA Explorer is back in a few minutes"
LATER = "the maintenance page will go up for everyone when it runs"


def needs_yes(data: dict | None, what: str, when: str = NOW) -> None:
    """Refused (428) until the request accepts the maintenance page."""
    if (data or {}).get("accept_maintenance"):
        return
    text = f"{what}: {when}. Go on?"
    abort(428, message=text, errors={"accept_maintenance": text})


def argv_says(argv: list[str]) -> tuple[str, str] | None:
    """What an eax command line does to the maintenance page (pure): (what, now|later), or None when nothing."""
    a = [str(x) for x in (argv or [])]
    if not a:
        return None
    head = a[0]
    if head in ("backup",):
        return "A backup of the whole installation", NOW
    if head in ("restore", "restore-app"):
        return "A restore", NOW
    if head in ("update", "rollback") and "--status" not in a:
        return "An update or a rollback", NOW
    if head in ("restart", "stop", "up", "clean-restart", "clean-run"):
        return f"eax {head}", "EA Explorer is unavailable for everyone until it is back up"
    if head == "maintenance" and a[1:2] == ["on"]:
        return "The maintenance page", "it goes up for everyone until it is taken down"
    if a[:3] == ["secrets", "rotate", "--all"]:
        return "Rotate all", NOW
    if a[:2] == ["secrets", "schedule"] and any(x in a for x in ("monthly", "quarterly", "--at")):
        return "Rotate all on a schedule", LATER
    if a[:2] == ["db", "integrity"] and "--fix" in a:
        return "The database's safe fixes (a backup first)", NOW
    if head == "test" and any(x in a for x in ("backup-restore", "restore", "full")):
        return "The backup and restore test", NOW
    if head in ("drill", "dr-pack"):
        return f"eax {head}", NOW
    return None


def argv_needs_yes(data: dict | None, argv: list[str], scheduled: bool = False) -> None:
    """An eax command line refused (428) until accepted, when it puts the maintenance page up (later, on a schedule)."""
    said = argv_says(argv)
    if said:
        needs_yes(data, said[0], LATER if scheduled else said[1])
