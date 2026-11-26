"""D948: the Logs page's list reads a compressed file's size once (runs 20 and 21, 26 Nov 2026: over 5,000 files of
100 KB, each size read through Docker Desktop's folder sharing, took over 30 s; GET /admin/logs/files answered 503)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from eaxcli import logkeep as K  # noqa: E402


def _kept(tmp: Path) -> Path:
    d = tmp / "containers" / "dms"
    d.mkdir(parents=True)
    (d / "2026-11-26.1.log.gz").write_bytes(b"x" * 10)
    (d / "2026-11-26.log").write_bytes(b"y" * 5)
    return d


def test_a_compressed_files_size_is_read_once(tmp_path, monkeypatch):
    monkeypatch.setattr(K, "_GZ_SIZES", {})
    d = _kept(tmp_path)
    assert K.files(tmp_path) == [{"service": "dms", "day": "2026-11-26", "size": 15}]
    (d / "2026-11-26.1.log.gz").write_bytes(b"x" * 99)          # never happens to a closed file: shows it is not read again
    (d / "2026-11-26.log").write_bytes(b"y" * 7)                # the day's open file is read every time
    assert K.files(tmp_path)[0]["size"] == 17
    assert K._GZ_SIZES == {"dms/2026-11-26.1.log.gz": 10}


def test_a_deleted_file_leaves_the_memory(tmp_path, monkeypatch):
    monkeypatch.setattr(K, "_GZ_SIZES", {})
    d = _kept(tmp_path)
    K.files(tmp_path)
    (d / "2026-11-26.1.log.gz").unlink()
    assert K.files(tmp_path)[0]["size"] == 5 and K._GZ_SIZES == {}


def test_the_operations_helper_reads_them_ahead_at_its_start():
    src = (Path(__file__).resolve().parents[3] / "services" / "ops" / "logsops.py").read_text(encoding="utf-8")
    assert 'threading.Thread(target=_warm, daemon=True, name="logs-sizes").start()' in src and "K.files(LOGS)" in src
