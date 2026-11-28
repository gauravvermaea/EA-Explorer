"""Release 14.6: ArchiMate's domain is domain everywhere, inside too (D959; owner, 26 Nov 2026, 17:54: "Add a next minor
release to move layer to domain"; 27 Nov 2026, 20:00: "Please fix layer everywhere and move it to domain. It is ok to
change see id, old rows and report function internal col names"; "This can be a breaking change"; "no migration will
be done"; "after this I will do clean restart and so will everyone else"). Nothing was deployed, so the migrations make
every name domain from the start (core.domains, library_models.domains, domain_id, the analyses' domain columns, the
report functions' own columns), there is no renaming migration and no code for the old names, and the seed's ids derive
from "domain". A clean restart is needed: a database or backup made before 14.6 does not upgrade."""

from __future__ import annotations

import re
from pathlib import Path

API = Path(__file__).resolve().parent.parent
REPO = API.parents[1]
OLD = re.compile(r"\blayers?\b|layer_|_layer\b", re.I)
# the word's other meanings, not ArchiMate's: Docker's image layers, an integration layer, a route layer, the icon named
# layers, reinsurance's excess layers, layers of control
OTHER = re.compile(r"layer_bytes|own layer|its own layer|layer cache|integration (and \w+ )?layer|API layer|Route layer|"
                   r"Debian fixes' layer|layers: \"M12|test_d959_layer_is_domain|['\"]layers['\"]|excess layers|"
                   r"layers of control|proprietary layers|OLD = re\.compile", re.I)


def _files() -> list[Path]:
    out = []
    for base in (API / "eax", API / "migrations", API / "tests", REPO / "services" / "web" / "src", REPO / "services" / "library",
                 REPO / "services" / "ops", REPO / "deploy", REPO / "eaxcli", REPO / "tools"):
        out += [p for p in base.rglob("*") if p.is_file() and p.suffix in (".py", ".sql", ".js", ".jsx", ".json", ".sh", ".yml")
                and "node_modules" not in p.parts and p.name != Path(__file__).name]
    return out


def test_no_code_or_migration_says_layer():
    bad = []
    for p in _files():
        for n, line in enumerate(p.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            if OLD.search(line) and not OTHER.search(line) and "player" not in line.lower().replace("players", "player"):
                bad.append(f"{p.relative_to(REPO)}:{n}: {line.strip()[:100]}")
    assert not bad, bad


def test_the_tables_are_made_as_domains():
    sql = (API / "migrations" / "sql" / "0002_metamodel.sql").read_text(encoding="utf-8")
    assert "CREATE TABLE core.domains (" in sql and "domain_id    bigint NOT NULL REFERENCES core.domains (id)" in sql
    assert not list((API / "migrations").rglob("*layer*"))                       # no renaming migration
    v = (API / "migrations" / "versions" / "0126_r14_6_standard_versions.py").read_text(encoding="utf-8")
    assert 'down_revision = "0125_release_14_5_0"' in v


def test_the_seed_ids_derive_from_domain():
    src = (API / "eax" / "seed" / "build.py").read_text(encoding="utf-8")
    assert 'ids("domain", domain)' in src and 'gid(key, "domain", n)' in src
    assert 'gid(k, "domain", n)' in (API / "eax" / "seed" / "togaf10.py").read_text(encoding="utf-8")


def test_no_code_for_the_old_names():
    from eax import change_log, databases
    assert "layers" not in change_log.TYPES and change_log.TYPES["domains"] == "Domain"
    assert not hasattr(databases, "RENAMES") and not hasattr(databases, "renames")
