"""D804: the regular expressions SonarQube found slow on some inputs (python:S8786, javascript:S8786) are rewritten as
string work or as expressions without the slow cases, and give exactly the same answers. Each test runs the old
expression (kept here as the specification) and the new code on thousands of generated texts and compares them."""

from __future__ import annotations

import importlib.util
import random
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))


def _tool(name: str):
    spec = importlib.util.spec_from_file_location(f"tool_{name}", REPO / "tools" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def texts(alphabet: list[str], runs: int = 4000, longest: int = 14, seed: int = 20261119):
    rnd = random.Random(seed)
    for _ in range(runs):
        yield "".join(rnd.choice(alphabet) for _ in range(rnd.randrange(longest)))


def same(alphabet, old, new, runs: int = 4000):
    for s in texts(alphabet, runs):
        a, b = old(s), new(s)
        assert a == b, f"{s!r}: old {a!r}, new {b!r}"


WS = [" ", "\t", "\n", "\x0b", " ", " "]          # spaces and breaks the old expressions also saw as \s
ONE_LINE = [" ", "\t", " "]                             # what splitlines() leaves inside one line


def _group(rx, s, n, flags=0):
    m = re.match(rx, s, flags)
    return m.group(n) if m else None


# ---------------------------------------------------------------- the eax command line
def test_config_secret_values():
    from eaxcli.backup_restore import secret_value
    old = re.compile(r"^\s*([A-Z0-9_]*(PASSWORD|SECRET|TOKEN)[A-Z0-9_]*|[A-Z0-9_]*_KEY)\s*=\s*(.+?)\s*$")
    same(["A", "PASSWORD", "TOKEN", "_KEY", "SECRET", "_", "1", "=", "x", "'", "a", *ONE_LINE],
         lambda s: (m.group(3) if (m := old.match(s)) else None), secret_value)


def test_config_values_of_the_drill(tmp_path):
    from eaxcli.drill import config_values
    old = re.compile(r"^\s*([A-Z0-9_]+)\s*=\s*(.*?)\s*$")
    f = tmp_path / "c.env"
    for s in texts(["A", "_", "1", "=", "x", "'", "\"", "a", *ONE_LINE], 1500):
        f.write_text(s, encoding="utf-8")
        want = {m.group(1): m.group(2).strip("'\"") for line in s.splitlines() if (m := old.match(line))}
        assert config_values(f) == want, repr(s)


def test_read_me_first_names():
    from eaxcli.packs import clean_name
    old = re.compile(r"^\d+\s+READ ME FIRST\s*-\s*(.*)\.(\w+)$", re.IGNORECASE)

    def before(name):
        m = old.match(name)
        return f"Retail - read me first ({m.group(1).strip()}).{m.group(2).lower()}" if m else re.sub(r"\s+", " ", name).strip()
    same(["00 READ ME FIRST - ", "1 read me first-", "x", ".", "pdf", " ", "é", "_", "-", "?"],
         before, lambda n: clean_name(n, "Retail"))


def test_flag_values_of_the_help():
    from eaxcli.commands import flag_value
    old = re.compile(r"^(--[\w-]+)(?:\|(--[\w-]+))?\s+(.+)$")

    def before(body):
        m = old.match(body)
        return ([f for f in (m.group(1), m.group(2)) if f], m.group(3).strip()) if m else None
    same(["--x", "--to", "|", "<v>", "a|b", " ", "\t", "-", "x"], before, flag_value)
    yes = re.compile(r"^(.*?)(\s*\[--yes\])?$")
    for s in texts(["a", " ", "[--yes]", "<v>"], 2000):
        m = yes.match(s)
        assert (m.group(1).strip(), bool(m.group(2))) == ((s[:-7] if s.endswith("[--yes]") else s).strip(), s.endswith("[--yes]"))


def test_secrets_masked_in_the_logs():
    from eaxcli.core import mask_assignment
    old = re.compile(r"((?:PASSWORD|SECRET|_KEY|URLENC)[A-Z_]*\s*[:=]\s*).*$")
    same(["PASSWORD", "_KEY", "URLENC", "SECRET", "A", "=", ":", "x", *WS], lambda s: old.sub(r"\1****", s), mask_assignment)


# ---------------------------------------------------------------- the API
def test_secret_lines_shown_as_set():
    from eax.auth import mask_secret_lines
    old = re.compile(r"^(\s*([A-Z0-9_]*(PASSWORD|SECRET|TOKEN|_KEY|PRIVATE|PASSPHRASE)[A-Z0-9_]*)\s*[=:]\s*)(.+)$", re.I | re.M)
    same(["password", "TOKEN", "_key", "x", "=", ":", "ſecret", "1", *WS], lambda s: old.sub(lambda m: m.group(1) + "(set)", s),
         mask_secret_lines, runs=8000)


def test_html_in_a_themes_css():
    from eax.branding import html_in_css
    old = re.compile(r"[<>]\s*/?\s*(style|script)|</|<!--|-->", re.I)
    same(["<", ">", "/", "style", "SCRIPT", "-->", "<!--", "-", "!", "x", *WS],
         lambda s: (m.start() if (m := old.search(s)) else -1), html_in_css, runs=8000)


def test_report_names_from_codes():
    from eax.report_designer import _split_capitals
    same(["A", "B", "c", "d", "1", "_", "É"], lambda s: re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", s), _split_capitals)


def test_alert_email_addresses():
    from eax.settings import is_email
    same(["a", "@", ".", " ", "\n", "b"], lambda s: bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", s)), is_email)


def test_markdown_table_rules():
    from eax.shipped_docs import _table_rule
    same(["|", ":", "-", " ", "\t", "x"], lambda s: bool(re.match(r"^\s*\|?\s*:?-{2,}", s)), _table_rule)


def test_reports_import_line():
    from eax.testing.reports_check import failed_count
    same(["1", "0", " failed", "x", " ", "failed", "٣"], lambda s: (m.group(1) if (m := re.search(r"(\d+) failed", s)) else None),
         failed_count)


def test_picture_names_without_brackets():
    from eax.testing.site_shots import without_last_brackets
    same(["(", ")", "a", " ", "\n", "x"], lambda s: re.sub(r"\s*\([^)]*\)\s*$", "", s), without_last_brackets, runs=8000)


def test_help_option_lines():
    from eax.testing.store import option_line
    old = re.compile(r"^(--\S+(?:\s+(?:\[[^\]]*\]|<[^>]*>|[A-Z]\b|--\S+))*)(?:\s+(.*))?$")

    def before(s):
        m = old.match(s)
        return (m.group(1), m.group(2) or "") if m else (s, "")
    same(["--x", "--", "[a b]", "[", "]", "<v>", "<", ">", "N", "Nb", "N,", " ", "x", "-"], before, option_line, runs=8000)


@pytest.mark.parametrize("old, new", [
    (r"^(#{1,4})\s+(.*)$", r"^(#{1,4})\s+(\S.*|)$"),
    (r"^(?:[-*+]|(\d+)[.)])\s+(.*)$", r"^(?:[-*+]|(\d+)[.)])\s+(\S.*|)$"),
    (r"^(\s*)([-*+]|\d+[.)])\s+(.*)$", r"^(\s*)([-*+]|\d+[.)])\s+(\S.*|)$"),
    (r"^(\s*)([-*]|\d+\.)\s+(.*)$", r"^(\s*)([-*]|\d+\.)\s+(\S.*|)$"),
    (r"^https?://[^\s/]+[^\s]*$", r"^https?://[^\s/]\S*$"),
])
def test_rewritten_expressions_match_the_same(old, new):
    alphabet = ["#", "-", "*", "+", "1", ".", ")", "x", "http://", "https://", "/", *WS]
    for s in texts(alphabet, 6000):
        a, b = re.match(old, s), re.match(new, s)
        assert (a and a.groups()) == (b and b.groups()), repr(s)
    for f in ("eax/doc_pdf.py", "eax/mcp_more.py", "eax/shipped_docs.py", "eax/pairing.py", "eax/sites.py", "eax/remote_instances.py"):
        assert old not in (REPO / "services/api" / f).read_text(encoding="utf-8")


def test_markdown_headings_found_in_a_document():
    for s in texts(["#", "##", "x", " ", "\n", "\t"], 6000):
        assert re.findall(r"^#{1,4}\s+(.*)$", s, re.M) == re.findall(r"^#{1,4}\s+(\S.*|)$", s, re.M), repr(s)


def test_headings_with_closing_hashes():
    old = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
    new = re.compile(r"^(#{1,6})\s+(\S.*|)$")
    for s in texts(["#", "x", " ", "\t", "##"], 6000):
        a, b = old.match(s), new.match(s)
        assert (a and (a.group(1), a.group(2))) == (b and (b.group(1), b.group(2).rstrip().rstrip("#").rstrip())), repr(s)


def test_numbers_of_a_drawing_path():
    old, new = r"[MLHVACZ]|-?\d*\.?\d+", r"[MLHVACZ]|-?(?:\d+(?:\.\d+)?|\.\d+)"
    assert new in (REPO / "services/api/eax/view_picture.py").read_text(encoding="utf-8")
    same(["M", "L", "1", "2", ".", "-", " ", ",", "Z", "٣"], lambda s: re.findall(old, s), lambda s: re.findall(new, s))


def test_trailing_punctuation_of_names():
    same([".", ",", ";", ":", "a", " "], lambda s: re.sub(r"[.,;:]+$", "", s), lambda s: s.rstrip(".,;:"))


# ---------------------------------------------------------------- the test bench and the tools
def test_down_revision_of_a_migration():
    from testbench.lifecycle import down_revision
    old = re.compile(r"^down_revision\s*=\s*(.+)$", re.M)
    same(["down_revision", " = ", "=", "'0108'", "None", " ", "\n", "x", "\t"],
         lambda s: (m.group(1) if (m := old.search(s)) else None), down_revision, runs=8000)


def test_first_heading_of_a_printed_guide():
    m = _tool("build_manuals")
    same(["#", "##", " ", "\n", "x", "\t"], lambda s: re.sub(r"^#{1,2}\s+.*\n", "", s, count=1), m.without_first_heading, runs=8000)


def test_help_inventory_keys_and_stars():
    m = _tool("help_inventory")

    def old_norm(text):
        t = re.sub(r"\s+", " ", text).strip()
        return re.sub(r"(\s*[:…]|\.\.\.)$", "", t).strip()
    same(["a", " ", ":", "…", ".", "\n"], old_norm, m.norm)
    same(["(*)", "*", "(", ")", " ", "a", "\t"], lambda s: re.sub(r"\s*\(\*\)|\s*\*", "", s), m.without_stars)


# ---------------------------------------------------------------- the screens (the same check in JavaScript)
def test_the_screens_text_scans_give_the_same_answers():
    node = shutil.which("node")
    if not node:
        pytest.skip("no node here")
    out = subprocess.run([node, str(REPO / "services/web/tests/text_scans.test.mjs")], capture_output=True, text=True, timeout=120)
    assert out.returncode == 0, out.stdout + out.stderr
