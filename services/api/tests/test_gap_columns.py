"""Gap and common analyses read their own tables' columns (owner, 12 Nov 2026: making a gap analysis said "column
"domain" does not exist"). Until Release 14.6 core.gap_items and core.common_items kept the domain in a column named
layer; migration 0126 renamed it domain (D959), so the queries now read domain and none reads layer."""

import re
from pathlib import Path

EAX = Path(__file__).resolve().parents[1] / "eax"


def test_no_query_reads_a_layer_column_from_the_analysis_tables():
    bad = []
    for f in ("gaps.py", "commons.py"):
        src = (EAX / f).read_text(encoding="utf-8")
        for sql in re.findall(r'"""(.*?)"""', src, re.S):
            if re.search(r"(FROM|INTO) core\.(gap|common)_items", sql) and re.search(r"\blayer\b", sql):
                bad.append(f"{f}: {' '.join(sql.split())[:120]}")
    assert not bad, bad
    for f in ("gaps.py", "commons.py"):
        assert "layer AS domain" not in (EAX / f).read_text(encoding="utf-8")
