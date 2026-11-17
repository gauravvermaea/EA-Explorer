"""Logo and branding (R5.7-B1): the logo, the browser tab's icon and the themes Super Admins add.

Revision ID: 0100_r5_7_branding
Revises: 0099_release_5_6_0
Create Date: 2026-11-17

The SQL lives in migrations/sql/0100_r5_7_branding.sql.
"""

from pathlib import Path

from alembic import op

revision = "0100_r5_7_branding"
down_revision = "0099_release_5_6_0"
branch_labels = None
depends_on = None

SQL_DIR = Path(__file__).resolve().parent.parent / "sql"


def upgrade() -> None:
    raw = op.get_bind().connection.driver_connection  # the psycopg 3 connection
    raw.execute((SQL_DIR / "0100_r5_7_branding.sql").read_text(encoding="utf-8"))


def downgrade() -> None:
    raw = op.get_bind().connection.driver_connection
    raw.execute("DROP TABLE IF EXISTS core.branding_themes; DROP TABLE IF EXISTS core.branding_files")
