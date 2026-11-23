"""Release 12: the base improvements (R12.4, D889): project management (settings with RACI and gates chosen at setup and
the roadmap's period, a plan of the phases, milestones, RACI, status reports) and maps always live (an item's live
view); a Risk record "describes" the risk Assessment in a model (the risk register)."""

from pathlib import Path

from alembic import op

revision = "0119_r12_project_management"
down_revision = "0118_r12_agile_dorp"
branch_labels = None
depends_on = None

SQL_DIR = Path(__file__).resolve().parent.parent / "sql"


def upgrade() -> None:
    raw = op.get_bind().connection.driver_connection  # the psycopg 3 connection
    raw.execute((SQL_DIR / "0119_r12_project_management.sql").read_text(encoding="utf-8"))


def downgrade() -> None:
    raw = op.get_bind().connection.driver_connection
    for t in ("status_reports", "raci", "milestones", "phase_plans", "pm_settings"):
        raw.execute(f"DROP TABLE IF EXISTS proj.{t}")
    for t in ("items", "lib_items"):
        raw.execute(f"ALTER TABLE proj.{t} DROP COLUMN IF EXISTS live_view")
    for c in ("togaf_roles", "togaf_levels"):
        raw.execute(f"ALTER TABLE personal.user_skills DROP COLUMN IF EXISTS {c}")
