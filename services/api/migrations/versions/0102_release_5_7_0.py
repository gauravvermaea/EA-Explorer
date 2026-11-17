"""Version 5.7.0: Release 5.7, view icons, branding, customer journeys, the deck tools (records the version only).

Revision ID: 0102_release_5_7_0
Revises: 0101_r5_7_journeys
Create Date: 2026-11-17

The SQL lives in migrations/sql/0102_release_5_7_0.sql.
"""

from pathlib import Path

from alembic import op

revision = "0102_release_5_7_0"
down_revision = "0101_r5_7_journeys"
branch_labels = None
depends_on = None

SQL_DIR = Path(__file__).resolve().parent.parent / "sql"


def upgrade() -> None:
    raw = op.get_bind().connection.driver_connection  # the psycopg 3 connection
    raw.execute((SQL_DIR / "0102_release_5_7_0.sql").read_text(encoding="utf-8"))


def downgrade() -> None:
    raw = op.get_bind().connection.driver_connection
    raw.execute("DELETE FROM core.schema_versions WHERE version = '5.7.0'")
