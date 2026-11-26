"""D939: self-test 18's DR-01, IT operations and Change manager dashboards answered "column x.layer does not exist".
rpt.f_dependencies read rpt.entities.layer, renamed type_domain in 0032 (ArchiMate 4 says domain, D391); PostgreSQL
does not check a SQL function's body when a column it reads is renamed, so nothing failed until a report ran it. Every
report function's latest body is checked here: no alias of a view that 0032 renamed reads the old column."""

import re
from pathlib import Path

SQL = Path(__file__).resolve().parents[1] / "migrations" / "sql"
# the columns 0032 renamed, by view (ALTER VIEW ... RENAME COLUMN old TO new)
RENAMED = {}
for m in re.finditer(r"ALTER VIEW (rpt\.\w+) RENAME COLUMN (\w+) TO (\w+);", (SQL / "0032_repository_tags.sql").read_text("utf-8")):
    RENAMED.setdefault(m.group(1), set()).add(m.group(2))


def _latest_bodies() -> dict[str, tuple[str, str]]:
    """Each rpt function's last definition in migration order: its file and its body."""
    out = {}
    for f in sorted(SQL.glob("*.sql")):
        text = f.read_text("utf-8")
        for m in re.finditer(r"CREATE (?:OR REPLACE )?FUNCTION (rpt\.\w+)\(.*?\$\$(.*?)\$\$", text, re.S):
            out[m.group(1)] = (f.name, m.group(2))
    return out


def test_the_renamed_columns_are_known():
    assert "layer" in RENAMED["rpt.entities"] and "layer_code" in RENAMED["rpt.entity_std"]


def test_no_report_function_reads_a_renamed_column():
    wrong = []
    for name, (file, body) in _latest_bodies().items():
        for view, cols in RENAMED.items():
            for alias in re.findall(rf"\b{re.escape(view)}\s+(?:AS\s+)?(\w+)", body):
                if alias.upper() in {"ON", "WHERE", "JOIN", "LEFT", "GROUP", "ORDER"}:
                    continue
                for col in cols:
                    if re.search(rf"\b{alias}\.{col}\b", body):
                        wrong.append(f"{name} ({file}): {alias}.{col} of {view}")
    assert not wrong, wrong


def test_the_dependencies_function_reads_the_domain_and_says_domain():
    file, body = _latest_bodies()["rpt.f_dependencies"]
    assert file == "0124_r14_5_dependencies_domain.sql" and "x.type_domain," in body and "x.layer" not in body
    sql = (SQL / file).read_text("utf-8")
    assert "domain text, lifecycle text" in sql and "layer text" not in sql     # its own column says domain (owner, 17:49)
    assert "DROP FUNCTION IF EXISTS rpt.f_dependencies(text, integer);" in sql
    assert "GRANT EXECUTE ON FUNCTION rpt.f_dependencies(text, integer) TO eax_report;" in sql
    reports = (SQL.parents[1] / "eax" / "setup" / "superset_reports.py").read_text("utf-8")
    assert "entity, entity_type, domain, lifecycle" in reports and "layer AS domain" not in reports


def test_the_migration_follows_release_14():
    v = (SQL.parent / "versions" / "0124_r14_5_dependencies_domain.py").read_text("utf-8")
    assert 'down_revision = "0123_release_14_0_0"' in v and "0124_r14_5_dependencies_domain.sql" in v
