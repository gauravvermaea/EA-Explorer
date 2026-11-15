"""R5.24 (bug, 15 Nov 2026): after the clean rebuild "the site can't be reached". The web log's day (R5.6) was written
`map $time_iso8601 $eax_day { ~^(\\d{4}-...) $1; ... }`: a regular expression with { } not in quotes, which nginx reads
as the start of a block, so the proxy refused its configuration and never started. These checks read the template the
way nginx does."""
import re
from pathlib import Path

TEMPLATE = Path(__file__).resolve().parents[3] / "deploy/proxy/templates/default.conf.template"


def tokens(text: str):
    """nginx's tokens: comments dropped, quoted strings kept whole, { } ; their own tokens. The template's ${EAX_...}
    (filled in by the image's envsubst at start) is replaced first."""
    text = re.sub(r"\$\{EAX_[A-Z0-9_]+\}", "x", text)
    out, i, n = [], 0, len(text)
    while i < n:
        c = text[i]
        if c.isspace():
            i += 1
        elif c == "#":
            while i < n and text[i] != "\n":
                i += 1
        elif c in "{};":
            out.append((c, False))
            i += 1
        elif c in "\"'":
            j = i + 1
            while j < n and text[j] != c:
                j += 2 if text[j] == "\\" else 1
            out.append((text[i + 1:j], True))
            i = j + 1
        else:
            j = i
            while j < n and not text[j].isspace() and text[j] not in "{};\"'":
                j += 1
            if text[j:j + 1] in "\"'" and j > i:                 # a quote inside a word belongs to it in nginx
                q = text[j]
                k = text.index(q, j + 1)
                j = k + 1
                while j < n and not text[j].isspace() and text[j] not in "{};":
                    j += 1
            out.append((text[i:j], False))
            i = j
    return out


def test_a_regular_expression_with_braces_is_quoted():
    toks = tokens(TEMPLATE.read_text(encoding="utf-8"))
    for k, (t, quoted) in enumerate(toks[:-1]):
        nxt = toks[k + 1]
        if not quoted and t.startswith("~") and nxt == ("{", False):
            raise AssertionError(f"an unquoted regular expression runs into a brace: {t!r}")


def test_the_blocks_close_as_nginx_reads_them():
    depth = 0
    for t, quoted in tokens(TEMPLATE.read_text(encoding="utf-8")):
        if not quoted and t == "{":
            depth += 1
        elif not quoted and t == "}":
            depth -= 1
            assert depth >= 0, "a } closes nothing"
    assert depth == 0


def test_every_map_line_is_a_pair():
    """Inside each map block every entry is exactly a source and a value (the broken line gave a block instead)."""
    toks = tokens(TEMPLATE.read_text(encoding="utf-8"))
    k = 0
    while k < len(toks):
        if toks[k] == ("map", False):
            j = k + 1
            while toks[j] != ("{", False):
                j += 1
            j += 1
            entry = []
            while toks[j] != ("}", False):
                assert toks[j] != ("{", False), f"a block inside a map near {toks[k + 2][0]}"
                if toks[j] == (";", False):
                    assert len(entry) == 2 or entry[0][0] in ("hostnames", "volatile"), f"map entry {entry}"
                    entry = []
                else:
                    entry.append(toks[j])
                j += 1
            k = j
        k += 1


def test_the_web_log_day_is_still_taken_from_the_time():
    text = TEMPLATE.read_text(encoding="utf-8")
    assert '"~^(\\d{4}-\\d{2}-\\d{2})"  $1;' in text
    assert "access_log /var/log/eax-web/$eax_day.log eax_web if=$eax_web_logged;" in text
