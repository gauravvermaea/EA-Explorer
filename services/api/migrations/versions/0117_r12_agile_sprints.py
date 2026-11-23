"""Release 12: architecture in sprints for an Agile project (R12.2, D879).

Revision ID: 0117_r12_agile_sprints
Revises: 0116_release_11_0_0
Create Date: 2026-11-22

The SQL lives in migrations/sql/0117_r12_agile_sprints.sql.
"""

from pathlib import Path

from alembic import op

revision = "0117_r12_agile_sprints"
down_revision = "0116_release_11_0_0"
branch_labels = None
depends_on = None

SQL_DIR = Path(__file__).resolve().parent.parent / "sql"


def upgrade() -> None:
    raw = op.get_bind().connection.driver_connection  # the psycopg 3 connection
    raw.execute((SQL_DIR / "0117_r12_agile_sprints.sql").read_text(encoding="utf-8"))


def downgrade() -> None:
    raw = op.get_bind().connection.driver_connection
    for t in ("sprint_decisions", "backlog_items", "sprints", "agile_settings"):
        raw.execute(f"DROP TABLE IF EXISTS proj.{t}")
