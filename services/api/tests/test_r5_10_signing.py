"""R5.10 (owner, 15 Nov 2026, D685: "we need a command in eax so that consumers can sign deployments if they want we
wont"): eax sign / eax verify, and the updater refusing an unsigned or changed version once a key is trusted."""

import os
import stat
import sys
import textwrap
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))

from eaxcli import signing as S  # noqa: E402

# a stand-in for OpenSSH's ssh-keygen -Y sign / -Y verify: the "signature" is the SHA-256 of the key and the data
FAKE = textwrap.dedent('''\
    #!/usr/bin/env python3
    import hashlib, sys
    a = sys.argv[1:]
    if a[:2] == ["-Y", "sign"]:
        key, data = a[a.index("-f") + 1], a[-1]
        pub = open(key + ".pub").read().split()[1]
        open(data + ".sig", "w").write(hashlib.sha256((pub + open(data).read()).encode()).hexdigest())
        sys.exit(0)
    if a[:2] == ["-Y", "verify"]:
        signers = open(a[a.index("-f") + 1]).read().split()
        sig = open(a[a.index("-s") + 1]).read()
        data = sys.stdin.read()
        ok = any(hashlib.sha256((k + data).encode()).hexdigest() == sig for k in signers[2::3])
        sys.exit(0 if ok else 1)
    sys.exit(2)
''')


@pytest.fixture
def keys(tmp_path, monkeypatch):
    bindir = tmp_path / "bin"
    bindir.mkdir()
    fake = bindir / "ssh-keygen"
    fake.write_text(FAKE)
    fake.chmod(fake.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setenv("PATH", f"{bindir}{os.pathsep}{os.environ['PATH']}")
    install = tmp_path / "install"
    (install / "work").mkdir(parents=True)
    monkeypatch.setenv("EAX_PERSIST_DIR", str(tmp_path / "persist"))
    monkeypatch.delenv("EAX_SIGNATURES_DIR", raising=False)
    key = tmp_path / "k"
    key.write_text("private")
    (tmp_path / "k.pub").write_text("ssh-ed25519 AAAAgood release-team\n")
    release = tmp_path / "release"
    (release / "services/api").mkdir(parents=True)
    (release / "services/api/version.toml").write_text('version = "5.0.0"\n')
    (release / "README.md").write_text("hello\n")
    (release / ".git").mkdir()
    (release / ".git/ignored").write_text("x")
    return install, key, release


@pytest.mark.skipif(os.name == "nt", reason="the stand-in ssh-keygen is a script")
def test_sign_trust_and_verify(keys):
    install, key, release = keys
    assert S.verify("5.0.0", release, install) == (True, "no trusted key: signing is not used here")   # optional
    S.trust(Path(str(key) + ".pub"), install)
    ok, why = S.verify("5.0.0", release, install)
    assert not ok and "not signed" in why
    m = S.sign("5.0.0", key, folder=release, root=install)
    assert m.name == "5.0.0.manifest" and (m.parent / "5.0.0.manifest.sig").exists()
    assert ".git/ignored" not in m.read_text() and "README.md" in m.read_text()
    assert S.verify("5.0.0", release, install)[0]
    (release / "README.md").write_text("changed\n")
    ok, why = S.verify("5.0.0", release, install)
    assert not ok and "README.md" in why
    (release / "README.md").write_text("hello\n")
    (S.trusted_dir(install) / "k.pub").write_text("ssh-ed25519 AAAAother someone-else\n")
    ok, why = S.verify("5.0.0", release, install)
    assert not ok and "does not verify" in why


def test_only_openssh_public_keys_are_trusted(tmp_path, monkeypatch):
    monkeypatch.setenv("EAX_PERSIST_DIR", str(tmp_path / "p"))
    bad = tmp_path / "x.pub"
    bad.write_text("-----BEGIN PUBLIC KEY-----")
    with pytest.raises(S.SignError):
        S.trust(bad, tmp_path)


def test_the_manifest_lists_every_file_with_its_sha256(tmp_path):
    (tmp_path / "a").mkdir()
    (tmp_path / "a/b.txt").write_bytes(b"abc")
    (tmp_path / "work").mkdir()
    (tmp_path / "work/x").write_text("not part of a release")
    text = S.manifest(tmp_path, "1.0.0").splitlines()
    assert text[:2] == [S.HEADER, "version: 1.0.0"]
    assert text[3:] == ["ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad  a/b.txt"]


def test_the_updater_checks_before_anything_changes():
    src = (REPO / "eaxcli/updater.py").read_text()
    co = src.split("def checkout(")[1].split("def _signed(")[0]
    assert co.index("self._signed(ref, sha, Path(tmp.name))") < co.index('self.env.git("checkout", "--force"')
    assert co.index("self._signed(ref, sha, staging)") < co.index("for f in sorted(new):")
    assert "from eaxcli import signing as S" in src


def test_every_form_has_sign_and_verify():
    assert "|sign|verify|" in (REPO / "eax.sh").read_text() and '"sign", "verify"' in (REPO / "eax.ps1").read_text()
    assert 'command in ("sign", "verify")' in (REPO / "eaxcli/main.py").read_text()
    h = (REPO / "eaxcli/help.txt").read_text()
    assert "### sign " in h and "### verify " in h
