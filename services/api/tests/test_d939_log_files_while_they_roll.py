"""D939: self-test 18, "GET /api/v1/admin/logs/files: every test role: it-admin: server error 500". The log keeper
closes a day's file at its size and compresses it (renamed, then .log.gz, the plain file removed) while the files are
listed: a file listed but gone before its size was read raised FileNotFoundError in the operations helper, a 500."""

import gzip
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))

from eaxcli import logkeep as K  # noqa: E402


def test_a_file_gone_between_the_listing_and_its_size_is_skipped(tmp_path):
    d = tmp_path / "containers" / "api"
    d.mkdir(parents=True)
    (d / "2026-11-26.1.log.gz").write_bytes(gzip.compress(b"x" * 10))
    (d / "2026-11-26.log").symlink_to(d / "gone.log")          # listed, but not there when its size is read
    (d / "2026-11-25.log").write_text("y" * 4)
    got = K.files(tmp_path)
    assert {(x["service"], x["day"]) for x in got} == {("api", "2026-11-26"), ("api", "2026-11-25")}
    assert next(x for x in got if x["day"] == "2026-11-26")["size"] == (d / "2026-11-26.1.log.gz").stat().st_size


def test_a_day_compressed_since_it_was_listed_is_read_from_its_gz(tmp_path):
    f = tmp_path / "2026-11-25.log"
    f.with_name(f.name + ".gz").write_bytes(gzip.compress(b"2026-11-25T10:00:00 one\n2026-11-25T10:01:00 two\n"))
    assert [ln.strip() for ln in K._lines(f)] == ["2026-11-25T10:00:00 one", "2026-11-25T10:01:00 two"]


def test_a_file_gone_altogether_reads_as_nothing(tmp_path):
    assert list(K._lines(tmp_path / "2026-11-24.3.log")) == []
