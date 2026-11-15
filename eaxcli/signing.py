"""Signed deployments, the organisation's own (R5.10, D685: "we need a command in eax so that consumers can sign
deployments if they want we wont").

The project does not sign its releases. An organisation that wants only versions it has checked to be installed:

  1. makes a key pair once, kept by its release or security team (never on an installation):
         eax sign keygen [<file>]                     (OpenSSH's ssh-keygen, Ed25519, a passphrase asked)
  2. trusts the public key on each installation:
         eax sign trust <file.pub>                    -> persist/keys/trusted/ (persist/ survives resets and updates)
  3. signs each version it has checked, on a machine with the private key and a copy of the repository:
         eax sign <version> --key <file> [--out <folder>]
     A manifest of every file of that version (SHA-256) is written and signed: <version>.manifest and
     <version>.manifest.sig. They are copied to each installation's signatures folder (persist/keys/signatures, or
     the folder EAX_SIGNATURES_DIR names: a share every installation reads).
  4. from then on `eax update` (and the Updates page, which runs the same updater) refuses a version whose signature is
     missing, does not verify against a trusted key, or whose files differ from its manifest, before anything is
     changed. With no trusted key nothing changes: signing is optional.

`eax verify <version>` checks one by hand. Standard library and OpenSSH's ssh-keygen (-Y sign / -Y verify) only, so it
runs in every form of eax and in the updater's container.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NAMESPACE = "eax-release"
PRINCIPAL = "eax-release"
EXCLUDE = (".git/", "work/", "persist/", "logs/", "node_modules/", "__pycache__/")
HEADER = "EA Explorer release manifest (R5.10)"


class SignError(Exception):
    """A signing problem, said plainly."""
    pass


def keys_dir(root: Path | None = None) -> Path:
    """Where signing keys are kept (persist/keys)."""
    from . import persist
    return persist.folder(root or ROOT) / "keys"


def trusted_dir(root: Path | None = None) -> Path:
    """Where the trusted public keys are."""
    return keys_dir(root) / "trusted"


def signatures_dir(root: Path | None = None) -> Path:
    """Where releases' signatures are (EAX_SIGNATURES_DIR, else persist/keys/signatures)."""
    given = os.environ.get("EAX_SIGNATURES_DIR")
    if not given:
        from . import persist
        given = persist._config_value(root or ROOT, "EAX_SIGNATURES_DIR")
    return Path(given) if given else keys_dir(root) / "signatures"


def trusted_keys(root: Path | None = None) -> list[Path]:
    """The trusted public keys."""
    d = trusted_dir(root)
    return sorted(d.glob("*.pub")) if d.is_dir() else []


def _skip(rel: str) -> bool:
    return rel.startswith(EXCLUDE) or "/__pycache__/" in rel or rel.endswith(".pyc")


def manifest(folder: Path, version: str) -> str:
    """Every file of a version with its SHA-256, sorted: what is signed."""
    lines = [HEADER, f"version: {version}", ""]
    for p in sorted(folder.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(folder).as_posix()
        if _skip(rel):
            continue
        h = hashlib.sha256()
        with open(p, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
        lines.append(f"{h.hexdigest()}  {rel}")
    return "\n".join(lines) + "\n"


def _ssh_keygen() -> str:
    exe = shutil.which("ssh-keygen")
    if not exe:
        raise SignError("ssh-keygen (OpenSSH) is not here: it is part of Windows 10 and later, Linux and macOS.")
    return exe


def _run(args: list[str], stdin: bytes | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(args, input=stdin, capture_output=True, timeout=120, check=False)


def keygen(path: Path) -> Path:
    """A new Ed25519 key pair; ssh-keygen asks for a passphrase. Returns the public key's file."""
    if path.exists():
        raise SignError(f"{path} exists already: choose another file.")
    path.parent.mkdir(parents=True, exist_ok=True)
    r = subprocess.run([_ssh_keygen(), "-t", "ed25519", "-C", "EA Explorer release signing", "-f", str(path)], check=False)
    if r.returncode != 0:
        raise SignError("ssh-keygen did not make the key.")
    return Path(str(path) + ".pub")


def trust(pub: Path, root: Path | None = None) -> Path:
    """Trusts a public key (an OpenSSH one only)."""
    text = pub.read_text(encoding="utf-8").strip()
    if not text.startswith(("ssh-ed25519 ", "ssh-rsa ", "ecdsa-sha2-")):
        raise SignError(f"{pub} is not an OpenSSH public key.")
    d = trusted_dir(root)
    d.mkdir(parents=True, exist_ok=True)
    out = d / pub.name
    out.write_text(text + "\n", encoding="utf-8")
    return out


def version_files(version: str, root: Path | None = None) -> tempfile.TemporaryDirectory:
    """The files of a version (its tag v<version>, or a commit) from the local repository, in a temporary folder."""
    root = root or ROOT
    ref = version if version.startswith("v") or len(version) >= 7 and all(c in "0123456789abcdef" for c in version) \
        else f"v{version}"
    tmp = tempfile.TemporaryDirectory(prefix="eax-sign-")
    archive = subprocess.run(["git", "-C", str(root), "archive", "--format=tar", ref], capture_output=True, check=False)
    if archive.returncode != 0:
        tmp.cleanup()
        raise SignError(f"git has no {ref} here: {archive.stderr.decode()[:200]}")
    import io
    import tarfile
    with tarfile.open(fileobj=io.BytesIO(archive.stdout)) as t:
        t.extractall(tmp.name, filter="data")
    return tmp


def name_of(version: str) -> str:
    """A version without its v."""
    return version.removeprefix("v")


def sign(version: str, key: Path, folder: Path | None = None, out: Path | None = None, root: Path | None = None) -> Path:
    """Writes <version>.manifest and its signature; returns the manifest's path."""
    out = out or signatures_dir(root)
    out.mkdir(parents=True, exist_ok=True)
    tmp = None
    if folder is None:
        tmp = version_files(version, root)
        folder = Path(tmp.name)
    try:
        m = out / f"{name_of(version)}.manifest"
        m.write_text(manifest(folder, name_of(version)), encoding="utf-8")
        sig = Path(str(m) + ".sig")
        sig.unlink(missing_ok=True)
        r = subprocess.run([_ssh_keygen(), "-Y", "sign", "-f", str(key), "-n", NAMESPACE, str(m)], check=False)
        if r.returncode != 0 or not sig.exists():
            raise SignError("ssh-keygen did not sign the manifest (wrong passphrase or key?).")
        return m
    finally:
        if tmp:
            tmp.cleanup()


def _allowed_signers(keys: list[Path]) -> str:
    return "".join(f"{PRINCIPAL} {k.read_text(encoding='utf-8').strip()}\n" for k in keys)


def verify(version: str, folder: Path, root: Path | None = None) -> tuple[bool, str]:
    """Whether the files in `folder` are the version the organisation signed: a trusted key, its signature, every file
    as in the manifest (none missing, none changed, none added). (True, why) or (False, why)."""
    keys = trusted_keys(root)
    if not keys:
        return True, "no trusted key: signing is not used here"
    sigs = signatures_dir(root)
    m = sigs / f"{name_of(version)}.manifest"
    sig = Path(str(m) + ".sig")
    if not m.exists() or not sig.exists():
        return False, f"{version} is not signed: no {m.name} and {sig.name} in {sigs}"
    with tempfile.NamedTemporaryFile("w", delete=False, suffix=".signers", encoding="utf-8") as f:
        f.write(_allowed_signers(keys))
        signers = f.name
    try:
        r = _run([_ssh_keygen(), "-Y", "verify", "-f", signers, "-I", PRINCIPAL, "-n", NAMESPACE, "-s", str(sig)],
                 stdin=m.read_bytes())
    finally:
        os.unlink(signers)
    if r.returncode != 0:
        return False, f"the signature of {version} does not verify against a trusted key ({r.stderr.decode()[:200].strip()})"
    want = m.read_text(encoding="utf-8")
    have = manifest(folder, name_of(version))
    if want != have:
        w, h = set(want.splitlines()[3:]), set(have.splitlines()[3:])
        changed = sorted({x.split("  ", 1)[1] for x in w ^ h if "  " in x})
        return False, f"{len(changed)} files differ from what was signed: {', '.join(changed[:8])}"
    return True, f"{version} is signed by a trusted key and every file is as signed"


def main(command: str, rest: list[str]) -> int:
    """eax sign keygen|trust|<version> ... and eax verify <version> [--folder <path>]."""
    try:
        if command == "verify":
            if not rest:
                raise SignError("eax verify <version> [--folder <path>]")
            version, folder = rest[0], _opt(rest, "--folder")
            tmp = None
            if folder is None:
                tmp = version_files(version)
                folder = tmp.name
            try:
                ok, why = verify(version, Path(folder))
            finally:
                if tmp:
                    tmp.cleanup()
            print(("OK: " if ok else "REFUSED: ") + why)
            return 0 if ok else 1
        if not rest:
            raise SignError("eax sign keygen [<file>] | trust <file.pub> | <version> --key <file> [--folder <path>] [--out <folder>]")
        if rest[0] == "keygen":
            pub = keygen(Path(rest[1]) if len(rest) > 1 else Path.home() / ".eax" / "eax-release-signing")
            print(f"Made the key pair. Keep the private key away from every installation; trust the public one on each:"
                  f"\n  eax sign trust {pub}")
            return 0
        if rest[0] == "trust":
            if len(rest) < 2:
                raise SignError("eax sign trust <file.pub>")
            print(f"Trusted: {trust(Path(rest[1]))}. From now on eax update installs only versions signed with it.")
            return 0
        key = _opt(rest, "--key")
        if not key:
            raise SignError("eax sign <version> --key <private key file>")
        folder, out = _opt(rest, "--folder"), _opt(rest, "--out")
        m = sign(rest[0], Path(key), Path(folder) if folder else None, Path(out) if out else None)
        print(f"Signed: {m} and {m.name}.sig. Copy both to each installation's {signatures_dir()} "
              "(or the shared folder EAX_SIGNATURES_DIR).")
        return 0
    except SignError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


def _opt(rest: list[str], name: str) -> str | None:
    return rest[rest.index(name) + 1] if name in rest and rest.index(name) + 1 < len(rest) else None
