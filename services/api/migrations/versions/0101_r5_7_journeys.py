"""Customer journey maps (R5.7-J1): journeys, their stages, parts, links, kinds of part, documents and events.

Revision ID: 0101_r5_7_journeys
Revises: 0100_r5_7_branding
Create Date: 2026-11-17

The SQL lives in migrations/sql/0101_r5_7_journeys.sql.
"""

from pathlib import Path

from alembic import op

revision = "0101_r5_7_journeys"
down_revision = "0100_r5_7_branding"
branch_labels = None
depends_on = None

SQL_DIR = Path(__file__).resolve().parent.parent / "sql"


def upgrade() -> None:
    raw = op.get_bind().connection.driver_connection  # the psycopg 3 connection
    raw.execute((SQL_DIR / "0101_r5_7_journeys.sql").read_text(encoding="utf-8"))


def downgrade() -> None:
    raw = op.get_bind().connection.driver_connection
    raw.execute("DROP TABLE IF EXISTS proj.journey_events, proj.journey_documents, proj.journey_part_kinds, proj.journey_links, "
                "proj.journey_items, proj.journey_stages, proj.journeys")
