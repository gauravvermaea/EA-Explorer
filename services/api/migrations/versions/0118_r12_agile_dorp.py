"""Release 12: sprints as the TOGAF Series Guide G210 has them: Demo, Outcome, Retrospective and Planning; Sprint zero; the
backlog's prioritisation (R12.2, D883)."""

from pathlib import Path

from alembic import op

revision = "0118_r12_agile_dorp"
down_revision = "0117_r12_agile_sprints"
branch_labels = None
depends_on = None

SQL_DIR = Path(__file__).resolve().parent.parent / "sql"


def upgrade() -> None:
    raw = op.get_bind().connection.driver_connection  # the psycopg 3 connection
    raw.execute((SQL_DIR / "0118_r12_agile_dorp.sql").read_text(encoding="utf-8"))


def downgrade() -> None:
    raw = op.get_bind().connection.driver_connection
    for t, c in (("sprints", "zero"), ("sprints", "demo_note"), ("sprints", "retrospective"), ("agile_settings", "priority_rule")):
        raw.execute(f"ALTER TABLE proj.{t} DROP COLUMN IF EXISTS {c}")
