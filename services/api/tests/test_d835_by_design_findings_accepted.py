"""D835: the 21 high findings of the full test of 21 Nov 2026 that are by design or false matches, accepted in writing
(owner, 21 Nov 2026, 20:29: "accept all, log them as a decision and also something in our conversation for next AI to
picl up").

Before: the security gate failed on 182 high or critical findings. After: these 21 are accepted until 21 May 2027, each
kept to its own file, so the same rule anywhere else still fails; the 161 package updates (Trivy) are not accepted and
still fail until R12.4 updates the images."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from eax.testing import security_gate

ACCEPTED = Path(__file__).resolve().parents[1] / "eax/testing/security_accepted.json"
BY_DESIGN = [
    ('semgrep', 'semgrep:dockerfile.security.missing-user.missing-user',
     'deploy/deployer/Dockerfile:10'),
    ('semgrep', 'semgrep:generic.secrets.security.detected-username-and-password-in-uri.detected-username-and-password-in-uri',
     'deploy/templates/eaexplorer.laptop.env:81'),
    ('semgrep', 'semgrep:python.lang.security.audit.dangerous-subprocess-use-tainted-env-args.dangerous-subprocess-use-tainted-env-args',
     'docs/images/db-tables-generate.py:17'),
    ('semgrep', 'semgrep:python.lang.security.audit.dangerous-subprocess-use-tainted-env-args.dangerous-subprocess-use-tainted-env-args',
     'docs/images/db-tables-generate.py:22'),
    ('semgrep', 'semgrep:python.lang.security.audit.dangerous-subprocess-use-tainted-env-args.dangerous-subprocess-use-tainted-env-args',
     'eaxcli/menu.py:178'),
    ('semgrep', 'semgrep:python.flask.security.injection.nan-injection.nan-injection',
     'services/api/eax/api/admin.py:324'),
    ('semgrep', 'semgrep:python.lang.security.unverified-ssl-context.unverified-ssl-context',
     'services/api/eax/console_cli.py:246'),
    ('semgrep', 'semgrep:generic.secrets.security.detected-google-gcm-service-account.detected-google-gcm-service-account',
     'services/api/eax/machine_access.py:526'),
    ('semgrep', 'semgrep:generic.secrets.security.detected-google-gcm-service-account.detected-google-gcm-service-account',
     'services/api/eax/machine_access.py:559'),
    ('semgrep', 'semgrep:dockerfile.security.missing-user-entrypoint.missing-user-entrypoint',
     'services/backup/Dockerfile:12'),
    ('semgrep', 'semgrep:dockerfile.security.last-user-is-root.last-user-is-root',
     'services/ops/Dockerfile:24'),
    ('semgrep', 'semgrep:python.lang.security.unverified-ssl-context.unverified-ssl-context',
     'testbench/shared.py:45'),
    ('gitleaks', 'gitleaks:generic-api-key',
     'services/api/tests/test_r5_6_backup_restore.py:194 commit 5e64dd529323'),
    ('gitleaks', 'gitleaks:generic-api-key',
     'services/api/tests/test_r5_17_security.py:122 commit 34bebd347090'),
    ('gitleaks', 'gitleaks:private-key',
     'services/api/tests/test_remote_instances.py:39 commit 4b17edfbae53'),
    ('gitleaks', 'gitleaks:private-key',
     'services/web/src/Farm.jsx:175 commit 4b17edfbae53'),
    ('gitleaks', 'gitleaks:private-key',
     'services/api/tests/test_deploy_page.py:19 commit c455d4f1b23f'),
    ('gitleaks', 'gitleaks:generic-api-key',
     'services/api/tests/test_console.py:56 commit 04585bee2785'),
    ('gitleaks', 'gitleaks:generic-api-key',
     'services/api/tests/test_console.py:59 commit 04585bee2785'),
    ('code', 'bandit:B402',
     '/app/eax/discovery_projects.py:27'),
    ('code', 'bandit:B321',
     '/app/eax/discovery_projects.py:426'),
]


def _found(source, fid, where, severity="high"):
    return {"source": source, "id": fid, "severity": severity, "title": fid, "where": where, "fix": True}


def test_the_21_by_design_findings_no_longer_fail_the_gate():
    got = security_gate.gate([_found(*f) for f in BY_DESIGN], security_gate.accepted([ACCEPTED]), date(2026, 11, 22))
    assert len(BY_DESIGN) == 21 and not got["failing"] and len(got["accepted"]) == 21


def test_each_is_kept_to_its_file_so_the_same_rule_elsewhere_still_fails():
    elsewhere = [_found("semgrep", "semgrep:dockerfile.security.last-user-is-root.last-user-is-root", "services/api/Dockerfile:9"),
                 _found("gitleaks", "gitleaks:generic-api-key", "services/api/eax/app.py:3 commit abc"),
                 _found("bandit", "bandit:B321", "/app/eax/backups.py:10")]
    got = security_gate.gate(elsewhere, security_gate.accepted([ACCEPTED]), date(2026, 11, 22))
    assert len(got["failing"]) == 3


def test_they_fail_again_after_the_review_date():
    got = security_gate.gate([_found(*BY_DESIGN[0])], security_gate.accepted([ACCEPTED]), date(2027, 5, 22))
    assert got["failing"] or got["expired"]


def test_the_package_updates_are_not_accepted():
    trivy = _found("trivy", "CVE-2026-113425", "image web")
    trivy["title"] = "nginx 1.30.6-r1 (fixed in 1.30.7-r0)"
    got = security_gate.gate([trivy], security_gate.accepted([ACCEPTED]), date(2026, 11, 22))
    assert len(got["failing"]) == 1
