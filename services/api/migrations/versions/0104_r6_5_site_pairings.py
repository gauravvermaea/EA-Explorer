"""Site pairings and sync batches (Release 6.5, D749).

Revision ID: 0104_r6_5_site_pairings
Revises: 0103_r5_7_branding_fonts
Create Date: 2026-11-17

The SQL lives in migrations/sql/0104_r6_5_site_pairings.sql.
"""

from pathlib import Path

from alembic import op

revision = "0104_r6_5_site_pairings"
down_revision = "0103_r5_7_branding_fonts"
branch_labels = None
depends_on = None

SQL_DIR = Path(__file__).resolve().parent.parent / "sql"


def upgrade() -> None:
    raw = op.get_bind().connection.driver_connection  # the psycopg 3 connection
    raw.execute((SQL_DIR / "0104_r6_5_site_pairings.sql").read_text(encoding="utf-8"))


def downgrade() -> None:
    raw = op.get_bind().connection.driver_connection
    raw.execute("DROP TABLE IF EXISTS core.sync_sent, core.sync_batches, core.site_pairings")
