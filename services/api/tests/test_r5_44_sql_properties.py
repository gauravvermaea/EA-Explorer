"""R5.44: the SQL page's tree wrote each database's, schema's and table's description under its name, and the
database drop-down carried it too, which cluttered the page (owner, 16 Nov 2026, 08:07: "can these be separate additional
window with properties to be seen. The window is very cluttered"). The tree and the drop-down now show names only; a
Properties panel under the tree shows the chosen database, schema, table or view: what it is for, rows and size."""
import json
from pathlib import Path

WEB = Path(__file__).resolve().parents[2] / "web" / "src"
SRC = (WEB / "Sql.jsx").read_text(encoding="utf-8")


def test_the_tree_shows_names_only():
    tree = SRC[SRC.index("function Tree("):SRC.index("function Properties(")]
    assert "tree-about" not in tree
    assert "onPick({ kind: \"schema\"" in tree and "onPick({ kind: \"object\"" in tree


def test_the_database_choice_shows_names_only():
    assert "{dbAbout[d] ? ` · ${dbAbout[d]}` : \"\"}" not in SRC
    assert "sql-db-about" not in SRC


def test_a_properties_panel_shows_what_is_chosen():
    props = SRC[SRC.index("function Properties("):SRC.index("export default function Sql()")]
    for k in ("What it is for", "Rows (about)", "Size", "Tables and views"):
        assert k in props
    assert "<Properties pick={pick} database={login.database}" in SRC
    assert ".sql-props" in (WEB / "styles.css").read_text(encoding="utf-8")


def test_help_mentions_the_panel():
    c = json.loads((WEB / "help" / "catalogue.json").read_text(encoding="utf-8"))
    assert "Properties" in json.dumps(c.get("page:#/sql") or c.get("page:#/admin/sql") or {})
