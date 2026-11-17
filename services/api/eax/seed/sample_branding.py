"""Logo and branding sample data (R5.7-B1, D729; AGENTS.md: every feature comes with seed data): laptop only, made once.

System admin > Branding shows one theme added by a Super Admin beside the four that ship: Meridian teal (sample), the
standard theme downloaded and changed as an organisation would. It is not chosen, so the screens keep the standard look
until someone picks it; nothing else (logo, name) is set.
"""

from __future__ import annotations

CSS = """/* Meridian teal (sample): the standard theme downloaded and changed, as an organisation would. */
:root {
  --ink: #1d2733; --quiet: #5b6775; --line: #d5e0de; --bg: #f4f8f7; --card: #ffffff;
  --accent: #0b6e4f; --accent-soft: #e3f2ed; --ok: #1e7b3c; --bad: #b3261e;
  font-family: system-ui, -apple-system, "Segoe UI", Roboto, Arial, sans-serif;
}
.topbar { border-bottom: 3px solid #0b6e4f; }
button.primary { background: #0b6e4f; border-color: #0b6e4f; }
"""


def run() -> list[str]:
    """Adds the sample theme once (kept as it is if someone changed it)."""
    from sqlalchemy import text

    from .. import branding as B
    from ..db import get_engine
    with get_engine().begin() as conn:
        if conn.execute(text("SELECT 1 FROM core.branding_themes WHERE slug = 'meridian-teal-sample'")).first():
            return ["Sample theme: already there"]
        B.save_theme(conn, "Meridian teal (sample)", CSS, "user_super_admin", slug="meridian-teal-sample")
    return ["Sample theme: Meridian teal (sample), added, not chosen"]
