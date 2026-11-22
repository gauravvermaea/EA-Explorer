"""System Admin > Secrets shows what applies to the installation's sign-in mode (Release 11, D877; the owner, 22 Nov 2026,
20:43: "should we not only show what is relevent or block the buttons and call out this is not applivcalble as it is
certificate mode or password mode").

In certificate mode, the services' own database logins sign in with certificates: their passwords are marked not used
(kept, and still rotated, for a switch back). The superuser and the replication login keep their passwords, as does
everything that is not a database login. In password mode nothing is marked. The page puts the mode's part first, and in
password mode the certificates are one line saying they are not used.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from eaxcli import secrets as S  # noqa: E402
from eaxcli import secretsrot as SR  # noqa: E402

PAGE = (ROOT / "services" / "web" / "src" / "Secrets.jsx").read_text(encoding="utf-8")
IDENT = (ROOT / "deploy" / "postgres" / "certificate" / "pg_ident.conf").read_text(encoding="utf-8")
HBA = (ROOT / "deploy" / "postgres" / "certificate" / "pg_hba.conf").read_text(encoding="utf-8")
OPS = (ROOT / "services" / "ops" / "ops.py").read_text(encoding="utf-8")

VALUES = {k: "x" for k in [*S.DB_LOGINS, *S.KEYCLOAK_CLIENTS, *S.NEEDS_A_PERSON, "EAX_MINIO_ROOT_PASSWORD"]}


def _rows(mode: str) -> dict[str, dict]:
    return {r["key"]: r for r in SR.rows(VALUES, {}, 90, mode=mode)}


def test_the_marked_logins_are_exactly_those_the_database_signs_in_by_certificate():
    # pg_ident.conf maps each service's certificate to the logins it may use: these, and only these, are not used
    by_certificate = {line.split()[2] for line in IDENT.splitlines() if line.strip() and not line.startswith("#")}
    marked = {S.DB_LOGINS[k] for k in S.NOT_USED_WITH_CERTIFICATES}
    assert marked == by_certificate & set(S.DB_LOGINS.values())
    assert marked == set(S.DB_LOGINS.values()) - {"postgres", "eax_replicator"}


def test_the_superuser_and_replication_login_still_sign_in_with_passwords():
    assert re.search(r"hostssl\s+all\s+postgres\s+\S+\s+scram-sha-256", HBA)
    assert re.search(r"hostssl\s+replication\s+eax_replicator\s+\S+\s+scram-sha-256", HBA)
    assert "EAX_DB_SUPERUSER_PASSWORD" not in S.NOT_USED_WITH_CERTIFICATES
    assert "EAX_REPLICATION_PASSWORD" not in S.NOT_USED_WITH_CERTIFICATES


def test_certificate_mode_marks_only_the_service_logins():
    rows = _rows("certificate")
    assert all(rows[k]["not_used"] for k in S.NOT_USED_WITH_CERTIFICATES)
    others = [k for k in rows if k not in S.NOT_USED_WITH_CERTIFICATES]
    assert others and not any(rows[k]["not_used"] for k in others)
    # still rotated by themselves, so a switch back works at once
    assert all(rows[k]["auto"] for k in S.NOT_USED_WITH_CERTIFICATES if S.kind_of(k, external_db=False) != "person")


def test_password_mode_marks_nothing_and_the_default_is_password():
    assert not any(r["not_used"] for r in _rows("password").values())
    assert not any(r["not_used"] for r in SR.rows(VALUES, {}, 90))


def test_the_page_and_the_command_line_are_given_the_mode():
    assert "SR.rows(secrets_, state, days, mode=mode)" in OPS
    assert "rows(values, read_state(), days, mode=mode)" in (ROOT / "eaxcli" / "secretsrot.py").read_text(encoding="utf-8")
    assert "not used: its certificate signs in" in (ROOT / "eaxcli" / "secrets.py").read_text(encoding="utf-8")


def test_the_page_puts_the_modes_part_first_and_says_what_is_not_used():
    assert "{certMode ? <>{certificatesPart}{passwordsPart}</> : <>{passwordsPart}{certificatesPart}</>}" in PAGE
    assert 'data-testid="certs-not-used"' in PAGE and "Not used: the services sign in with passwords" in PAGE
    assert "Not used while in certificate mode" in PAGE and "kept so you can switch back" in PAGE
    # the Rotate now button stays for a not-used login (kept fresh for a switch back): no not_used in its condition
    assert "{s.auto && s.set && <button" in PAGE
    # the front door's certificate is used in both modes: it is in the part that always shows
    passwords = PAGE[PAGE.index("const passwordsPart"):PAGE.index("const certificatesPart")]
    assert "<FrontCertificate />" in passwords
