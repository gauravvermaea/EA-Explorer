"""Release 14.6: which version of a standard each metamodel item belongs to (D965).

Revision ID: 0126_r14_6_standard_versions
Revises: 0125_release_14_5_0
Create Date: 2026-11-28

The SQL lives in migrations/sql/0126_r14_6_standard_versions.sql.
"""

from pathlib import Path

from alembic import op

revision = "0126_r14_6_standard_versions"
down_revision = "0125_release_14_5_0"
branch_labels = None
depends_on = None

SQL_DIR = Path(__file__).resolve().parent.parent / "sql"


def upgrade() -> None:
    raw = op.get_bind().connection.driver_connection  # the psycopg 3 connection
    raw.execute((SQL_DIR / "0126_r14_6_standard_versions.sql").read_text(encoding="utf-8"))


def downgrade() -> None:
    raise NotImplementedError("0126 adds the standard versions; a clean restart goes back (D964)")
