"""D952: a restore's swap takes no new session (the DR drill of 27 Nov 2026 failed: "database superset is being accessed
by other users"; Reports was still starting in the DR copy and connected again between the kick and the rename)."""

from __future__ import annotations

from pathlib import Path

RESTORE = (Path(__file__).resolve().parents[2] / "backup" / "restore.sh").read_text(encoding="utf-8").replace("\r\n", "\n")


def test_connections_are_shut_before_the_kick_and_the_rename():
    block = RESTORE.index('q "ALTER DATABASE \\"$DB\\" WITH ALLOW_CONNECTIONS false"')
    kick = RESTORE.index('at "$DB" kick "$DB"\n    at "$DB" q "ALTER DATABASE \\"$DB\\" RENAME TO \\"${DB}__before\\""')
    assert block < kick


def test_a_failed_restore_opens_every_live_database_again():
    rollback = RESTORE[RESTORE.index("rollback() {"):RESTORE.index('say "FAILED: nothing was changed')]
    assert 'for DB in $LIST; do at "$DB" exists "$DB" && at "$DB" q "ALTER DATABASE \\"$DB\\" WITH ALLOW_CONNECTIONS true"' in rollback
    assert rollback.index("RENAME TO \\\"$DB\\\"") < rollback.index("ALLOW_CONNECTIONS true")
