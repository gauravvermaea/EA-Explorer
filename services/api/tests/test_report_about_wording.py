"""The About text of every report reads as plain English (18 Nov 2026: a view's text said "Technology Usage view
view's stakeholders", the word doubled)."""

import re

from eax import report_about, report_defs


def test_no_report_about_text_repeats_a_word():
    for r in report_defs.REPORTS:
        about = report_about.about(r)
        for text in (about["use"], about["read"]):
            assert not re.search(r"\b(\w+) \1\b", text, re.I), (r["code"], text)
