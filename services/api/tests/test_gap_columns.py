"""Gap and common analyses read their own tables' columns (owner, 12 Nov 2026: making a gap analysis said "column
"domain" does not exist"). Since Release 14.6 (D959) core.gap_items and core.common_items keep it in a column named
domain from the start, and the queries read it by that name."""

import re
from pathlib import Path

EAX = Path(__file__).resolve().parents[1] / "eax"


def test_the_analysis_tables_are_read_by_their_domain_column():
    bad = []
    for f in ("gaps.py", "commons.py"):
        src = (EAX / f).read_text(encoding="utf-8")
        for sql in re.findall(r'"""(.*?)"""', src, re.S):
            if re.search(r"(FROM|INTO) core\.(gap|common)_items", sql) and re.search(r"\bla" + r"yer\b", sql):
                bad.append(f"{f}: {' '.join(sql.split())[:120]}")
    assert not bad, bad
    for f in ("gaps.py", "commons.py"):
        assert " AS domain" not in (EAX / f).read_text(encoding="utf-8")
