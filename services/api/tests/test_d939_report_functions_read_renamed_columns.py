"""D939: self-test 18's DR-01, IT operations and Change manager dashboards failed because a report function read a
view's column by its name before ArchiMate 4 (D391); PostgreSQL does not check a SQL function's body when a column it
reads is renamed. Since Release 14.6 (D959) the migrations make every name domain from the start, nothing is renamed,
and no report function, view or column has the old name."""

import re
from pathlib import Path

SQL = Path(__file__).resolve().parents[1] / "migrations" / "sql"
OLD = re.compile(r"\blayers?\b|layer_|_layer\b", re.I)


def _latest_bodies() -> dict[str, tuple[str, str]]:
    """Each rpt function's last definition in migration order: its file and its body."""
    out = {}
    for f in sorted(SQL.glob("*.sql")):
        text = f.read_text("utf-8")
        for m in re.finditer(r"CREATE (?:OR REPLACE )?FUNCTION (rpt\.\w+)\(.*?\$\$(.*?)\$\$", text, re.S):
            out[m.group(1)] = (f.name, m.group(2))
    return out


def test_no_report_function_reads_an_old_name():
    wrong = [f"{name} ({file})" for name, (file, body) in _latest_bodies().items() if OLD.search(body)]
    assert not wrong, wrong


def test_the_dependencies_function_reads_the_domain_and_says_domain():
    file, body = _latest_bodies()["rpt.f_dependencies"]
    assert file == "0124_r14_5_dependencies_domain.sql" and "x.type_domain," in body and not OLD.search(body)
    sql = (SQL / file).read_text("utf-8")
    assert "domain text, lifecycle text" in sql and not OLD.search(sql)     # its own column says domain (owner, 17:49)
    assert "DROP FUNCTION IF EXISTS rpt.f_dependencies(text, integer);" in sql
    assert "GRANT EXECUTE ON FUNCTION rpt.f_dependencies(text, integer) TO eax_report;" in sql
    reports = (SQL.parents[1] / "eax" / "setup" / "superset_reports.py").read_text("utf-8")
    assert "entity, entity_type, domain, lifecycle" in reports and not OLD.search(reports)


def test_the_migration_follows_release_14():
    v = (SQL.parent / "versions" / "0124_r14_5_dependencies_domain.py").read_text("utf-8")
    assert 'down_revision = "0123_release_14_0_0"' in v and "0124_r14_5_dependencies_domain.sql" in v
