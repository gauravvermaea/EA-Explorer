"""R5.20: watching the self-test browsers live.

Revision ID: 0086_r5_live_browser
Revises: 0085_r5_sizing
Create Date: 2026-11-15

The SQL lives in migrations/sql/0086_r5_live_browser.sql.
"""

from pathlib import Path

from alembic import op

revision = "0086_r5_live_browser"
down_revision = "0085_r5_sizing"
branch_labels = None
depends_on = None

SQL_DIR = Path(__file__).resolve().parent.parent / "sql"


def upgrade() -> None:
    raw = op.get_bind().connection.driver_connection  # the psycopg 3 connection
    raw.execute((SQL_DIR / "0086_r5_live_browser.sql").read_text(encoding="utf-8"))


def downgrade() -> None:
    raw = op.get_bind().connection.driver_connection
    raw.execute("DROP TABLE IF EXISTS tests.live_browsers, tests.live_controls")
