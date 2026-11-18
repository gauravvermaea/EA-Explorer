"""The integrity checks kept with the database maintenance runs (Release 6.6, R6.6.1, D750).

Revision ID: 0105_r6_6_db_integrity
Revises: 0104_r6_5_site_pairings
Create Date: 2026-11-17

The SQL lives in migrations/sql/0105_r6_6_db_integrity.sql.
"""

from pathlib import Path

from alembic import op

revision = "0105_r6_6_db_integrity"
down_revision = "0104_r6_5_site_pairings"
branch_labels = None
depends_on = None

SQL_DIR = Path(__file__).resolve().parent.parent / "sql"


def upgrade() -> None:
    raw = op.get_bind().connection.driver_connection  # the psycopg 3 connection
    raw.execute((SQL_DIR / "0105_r6_6_db_integrity.sql").read_text(encoding="utf-8"))


def downgrade() -> None:
    raw = op.get_bind().connection.driver_connection
    raw.execute("DELETE FROM core.db_maintenance_runs WHERE kind IN ('integrity', 'repair')")
    raw.execute("ALTER TABLE core.db_maintenance_runs DROP CONSTRAINT IF EXISTS db_maintenance_runs_kind_check")
    raw.execute("ALTER TABLE core.db_maintenance_runs ADD CONSTRAINT db_maintenance_runs_kind_check "
                "CHECK (kind IN ('check', 'tidy', 'compact', 'clear', 'locks'))")
