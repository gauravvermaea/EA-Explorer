"""Release 10: scenario planning and game theory, a project's studies kept as dated versions (D788, D818, D857).

Revision ID: 0113_r10_scenario_planning
Revises: 0112_release_8_0_0
Create Date: 2026-11-22

The SQL lives in migrations/sql/0113_r10_scenario_planning.sql.
"""

from pathlib import Path

from alembic import op

revision = "0113_r10_scenario_planning"
down_revision = "0112_release_8_0_0"
branch_labels = None
depends_on = None

SQL_DIR = Path(__file__).resolve().parent.parent / "sql"


def upgrade() -> None:
    raw = op.get_bind().connection.driver_connection  # the psycopg 3 connection
    raw.execute((SQL_DIR / "0113_r10_scenario_planning.sql").read_text(encoding="utf-8"))


def downgrade() -> None:
    # Clean rebuilds are the rule (D54); this removes what 0113 added.
    raw = op.get_bind().connection.driver_connection
    raw.execute("DROP TABLE IF EXISTS proj.sp_signpost_marks")
    raw.execute("DROP TABLE IF EXISTS proj.sp_runs")
