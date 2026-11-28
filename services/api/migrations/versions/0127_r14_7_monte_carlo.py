"""Release 14.7: Monte Carlo studies in a project, their runs, and the organisation's risk scale (D957, D962).

Revision ID: 0127_r14_7_monte_carlo
Revises: 0126_r14_6_standard_versions
Create Date: 2026-11-27

The SQL lives in migrations/sql/0127_r14_7_monte_carlo.sql.
"""

from pathlib import Path

from alembic import op

revision = "0127_r14_7_monte_carlo"
down_revision = "0126_r14_6_standard_versions"
branch_labels = None
depends_on = None

SQL_DIR = Path(__file__).resolve().parent.parent / "sql"


def upgrade() -> None:
    raw = op.get_bind().connection.driver_connection  # the psycopg 3 connection
    raw.execute((SQL_DIR / "0127_r14_7_monte_carlo.sql").read_text(encoding="utf-8"))


def downgrade() -> None:
    raw = op.get_bind().connection.driver_connection
    raw.execute("DROP TABLE IF EXISTS proj.mc_runs; DROP TABLE IF EXISTS proj.mc_studies; DROP TABLE IF EXISTS proj.mc_risk_scale")
