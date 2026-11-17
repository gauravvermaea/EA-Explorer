"""Fonts uploaded for the themes (R5.7-B1, D736).

Revision ID: 0103_r5_7_branding_fonts
Revises: 0102_release_5_7_0
Create Date: 2026-11-17

The SQL lives in migrations/sql/0103_r5_7_branding_fonts.sql.
"""

from pathlib import Path

from alembic import op

revision = "0103_r5_7_branding_fonts"
down_revision = "0102_release_5_7_0"
branch_labels = None
depends_on = None

SQL_DIR = Path(__file__).resolve().parent.parent / "sql"


def upgrade() -> None:
    raw = op.get_bind().connection.driver_connection  # the psycopg 3 connection
    raw.execute((SQL_DIR / "0103_r5_7_branding_fonts.sql").read_text(encoding="utf-8"))


def downgrade() -> None:
    raw = op.get_bind().connection.driver_connection
    raw.execute("DROP TABLE IF EXISTS core.branding_fonts")
