"""Release 14.6: ArchiMate's layer becomes domain inside the database too (D959, D941).

Revision ID: 0126_r14_6_layer_to_domain
Revises: 0125_release_14_5_0
Create Date: 2026-11-27

The SQL lives in migrations/sql/0126_r14_6_layer_to_domain.sql.
"""

from pathlib import Path

from alembic import op

revision = "0126_r14_6_layer_to_domain"
down_revision = "0125_release_14_5_0"
branch_labels = None
depends_on = None

SQL_DIR = Path(__file__).resolve().parent.parent / "sql"


def upgrade() -> None:
    raw = op.get_bind().connection.driver_connection  # the psycopg 3 connection
    raw.execute((SQL_DIR / "0126_r14_6_layer_to_domain.sql").read_text(encoding="utf-8"))


def downgrade() -> None:
    raise NotImplementedError("0126 renames layer to domain; restore the backup taken before the update to go back")
