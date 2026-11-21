"""D804: the smaller SonarQube fixes of Release 8, each shown to leave what EA Explorer does unchanged."""

from __future__ import annotations

import ast
import math
import random
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
API = REPO / "services" / "api"


def test_a_value_that_is_not_a_number_is_still_shown_as_text():
    from eax.sqlconsole import to_json_value
    for v in (1.5, 0.0, -2.25, 1e308):
        assert to_json_value(v) == v
    for v in (float("nan"), float("inf"), float("-inf")):
        assert to_json_value(v) == str(v)
    assert all((x == x) is (not math.isnan(x)) for x in (1.0, float("nan"), float("inf")))   # the old test, the same


def test_a_closeness_is_never_above_one_so_at_least_one_is_the_same_as_one():
    from eax.dedupe import closeness
    rnd = random.Random(804)
    words = ["Claims", "claims", "Platform", "CRM", "crm 2", "Policy", "admin", "Admin 2", " ", "x"]
    for _ in range(3000):
        a = " ".join(rnd.choice(words) for _ in range(rnd.randrange(1, 4)))
        b = " ".join(rnd.choice(words) for _ in range(rnd.randrange(1, 4)))
        s = closeness(a, b)
        assert 0.0 <= s <= 1.0 and (s >= 1.0) == (s == 1.0)


def test_mains_that_always_ended_well_still_end_with_exit_code_zero():
    for f in ("deploy/superset/eax_reports_init.py", "services/api/eax/jobs_schema.py", "services/api/eax/library_models.py",
              "services/api/eax/optimise.py", "services/api/eax/seed/later.py", "services/api/eax/seed/versions_demo.py"):
        src = (REPO / f).read_text(encoding="utf-8")
        main = next(n for n in ast.parse(src).body if isinstance(n, ast.FunctionDef) and n.name == "main")
        assert ast.unparse(main.returns) == "None", f
        assert all(r.value is None for r in ast.walk(main) if isinstance(r, ast.Return)), f
        tail = src[src.index('if __name__ == "__main__":'):]
        assert re.search(r"^\s+main\(", tail, re.M) and "sys.exit(main(" not in tail, f    # called, its nothing not passed on
    import subprocess  # a script that ends normally ends with exit code 0
    assert subprocess.run([sys.executable, "-c", "def main():\n    return\nmain()"]).returncode == 0


def test_the_odata_parser_step_is_named_comparison_and_not_compare():
    src = (API / "eax" / "odata.py").read_text(encoding="utf-8")
    assert "def comparison(self)" in src and "def compare(" not in src and "self.compare()" not in src


def test_regular_expressions_with_their_alternatives_grouped_match_the_same():
    pairs = [
        (r"/(backups?|restores?|export|download|package|packages|terminal|logs|sql|stats|files|repo-zip)(/|$)|\.(zip|xlsx|pdf|docx)$",
         r"(?:/(backups?|restores?|export|download|package|packages|terminal|logs|sql|stats|files|repo-zip)(/|$))|(?:\.(zip|xlsx|pdf|docx)$)", 0),
        (r"^/api/v1/(admin|operations|mcp|tests|updates|deploy|backups|restores)\b|/(download|export|zip|xlsx|csv|pdf)\b",
         r"(?:^/api/v1/(admin|operations|mcp|tests|updates|deploy|backups|restores)\b)|(?:/(download|export|zip|xlsx|csv|pdf)\b)", 0),
        (r"^#/break-glass\b|logout|sign-?out", r"(?:^#/break-glass\b)|logout|sign-?out", re.I),
        (r"(?ms)^##\s+Related\s*\n.*?(?=^#{1,2}\s|\Z)", r"(?ms)^##\s+Related\s*\n.*?(?=(?:^#{1,2}\s)|\Z)", 0),
        (r"\b(?:tabs|TABS|[A-Z_]*TABS|[a-z]+Tabs)\s*=\s*\[", r"\b(?:tabs|[A-Z_]*TABS|[a-z]+Tabs)\s*=\s*\[", 0),
    ]
    alphabet = ["/api/v1/", "admin", "/backups", "/", ".zip", "x", "#/break-glass", "LOGOUT", "sign-out", "\n", "## Related",
                "# ", "## ", " ", "tabs", "TABS", "X_TABS", "myTabs", "=", "[", "q"]
    rnd = random.Random(804)
    for old, new, flags in pairs:
        o, n = re.compile(old, flags), re.compile(new, flags)
        for _ in range(4000):
            s = "".join(rnd.choice(alphabet) for _ in range(rnd.randrange(10)))
            assert [m.span() + m.groups() for m in o.finditer(s)] == [m.span() + m.groups() for m in n.finditer(s)], (old, s)
            assert o.sub("~", s) == n.sub("~", s)


def test_the_screens_one_off_fixes():
    web = REPO / "services" / "web" / "src"
    surveys = (web / "Surveys.jsx").read_text(encoding="utf-8")
    assert "[String(a)]" in surveys and 'typeof a === "boolean" ? String(a) : String(a)' not in surveys
    for f in ("BreakGlass.jsx", "Logs.jsx", "Users.jsx"):             # the buttons that send their form say so
        assert '<button type="submit"' in (web / f).read_text(encoding="utf-8"), f
    auth, app = (web / "auth.js").read_text(encoding="utf-8"), (web / "App.jsx").read_text(encoding="utf-8")
    assert "export let " not in auth and "isKeycloakReachable()" in app
