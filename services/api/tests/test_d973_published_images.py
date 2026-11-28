"""D973 (Release 14.8.1): our eleven images (eax: D976) published from deploy/release/docker-bake.hcl by
.github/workflows/publish-images.yml, the published api, library and testrunner holding what a developer's compose
file mounts from this repository, and docs/images.md ("The images: what is ours and what we changed") kept right."""

from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
REL = REPO / "deploy" / "release"
BAKE = (REL / "docker-bake.hcl").read_text(encoding="utf-8")
FLOW = (REPO / ".github" / "workflows" / "publish-images.yml").read_text(encoding="utf-8")
PAGE = (REPO / "docs" / "images.md").read_text(encoding="utf-8")
COMPOSE = (REPO / "docker-compose.yml").read_text(encoding="utf-8")
OURS = ["api", "web", "backup", "library", "views", "ops", "drawio", "superset", "jenkins", "testrunner", "eax"]
DOCKERFILES = {"api": "services/api/Dockerfile", "web": "services/web/Dockerfile", "backup": "services/backup/Dockerfile",
               "library": "services/library/Dockerfile", "views": "services/views/Dockerfile", "ops": "services/ops/Dockerfile",
               "drawio": "deploy/drawio/Dockerfile", "superset": "deploy/superset/Dockerfile",
               "jenkins": "deploy/jenkins/Dockerfile", "testrunner": "services/api/Dockerfile.test",
               "eax": "deploy/eax/Dockerfile"}


def upstreams(dockerfile: str) -> list[str]:
    """The upstream images a Dockerfile builds on, its ARG defaults resolved."""
    text = (REPO / dockerfile).read_text(encoding="utf-8")
    args = dict(re.findall(r"^ARG (\w+)=(\S+)", text, re.M))
    out = []
    for ref in re.findall(r"^FROM (\S+)", text, re.M):
        m = re.fullmatch(r"\$\{(\w+)\}", ref)
        out.append(args[m.group(1)] if m else ref)
    return out


def test_the_eleven_images_are_published_and_only_ours():
    group = re.search(r'group "default" \{\s*targets = \[([^\]]*)\]', BAKE).group(1)
    assert re.findall(r'"([\w-]+)"', group) == OURS
    for name in OURS:
        assert f'target "{name}"' in BAKE and f'tags("{name}")' in BAKE
    for upstream in ("postgres", "keycloak", "valkey", "mayan", "nginx"):
        assert f'target "{upstream}"' not in BAKE                     # used as their makers publish them
    assert 'variable "PLATFORMS" { default = "linux/amd64,linux/arm64" }' in BAKE


def test_the_workflow_publishes_to_both_registries_when_a_release_is_tagged():
    assert 'tags: ["v*"]' in FLOW and "workflow_dispatch" in FLOW
    assert "registry: ghcr.io" in FLOW and "secrets.GITHUB_TOKEN" in FLOW and "packages: write" in FLOW
    assert "secrets.DOCKERHUB_TOKEN" in FLOW and "vars.DOCKERHUB_USERNAME" in FLOW and "vars.DOCKERHUB_PREFIX" in FLOW
    assert "docker buildx bake -f deploy/release/docker-bake.hcl --push" in FLOW
    assert "services/api/version.toml" in FLOW and "tag the version the code says" in FLOW
    assert "setup-qemu-action" in FLOW                               # ARM too
    assert "DOCKERHUB_TOKEN:" not in FLOW.replace("secrets.DOCKERHUB_TOKEN", "")   # never written out


def test_the_published_images_hold_what_a_developers_compose_mounts():
    copies = {}
    for f in REL.glob("*.Dockerfile"):
        for src, dst in re.findall(r"^COPY (\S+) (\S+)", f.read_text(encoding="utf-8"), re.M):
            copies[dst] = src
            ignore = (f.parent / (f.name + ".dockerignore")).read_text(encoding="utf-8")
            assert f"!{src}" in ignore, f"{f.name}: {src} is copied but its .dockerignore leaves it out"
            assert (REPO / src).exists(), src
    mounts = re.findall(r"- \./([\w./-]+):(/data/docs[\w./-]*|/data/ea-explorer-templates|/data/industry-packs|/testdata|/deploy)(?::ro)?\s",
                        COMPOSE)
    assert len(mounts) >= 12
    for src, dst in mounts:
        assert copies.get(dst) == src, f"compose mounts ./{src} at {dst}; the published image must hold it there"
    assert "togaf" not in " ".join(copies.values())                   # The Open Group's files: never in an image


def test_a_local_build_is_unchanged():
    for name in ("api", "library"):
        assert "COPY --from" not in (REPO / DOCKERFILES[name]).read_text(encoding="utf-8")
    assert "additional_contexts" not in COMPOSE


def test_the_page_names_every_upstream_and_what_we_change():
    for name, dockerfile in DOCKERFILES.items():
        assert f"| `{name}` |" in PAGE, name
        for up in upstreams(dockerfile):
            if up.lower() in ("base", "build"):
                continue
            assert f"`{up}`" in PAGE, f"docs/images.md does not name {up} ({dockerfile})"
    for default in re.findall(r"EAX_IMAGE_\w+:-([^}]+)\}", COMPOSE):
        assert f"`{default}`" in PAGE, f"docs/images.md does not name {default} (docker-compose.yml)"
    for words in ("our plugin", "the database drivers", "our plugins", "the test data", "exactly as its maker publishes it"):
        assert words in PAGE
