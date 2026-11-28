# The images: what is ours and what we changed

EA Explorer runs as a set of containers. Eleven of the images are **ours**: we build them, and we publish them for every
release to Docker Hub and to GitHub's registry, for Intel/AMD and ARM machines (D973). Every other image is used
**exactly as its maker publishes it**, at the version pinned in the compose file; for those we only add settings files,
mounted when the container starts. This page says which is which, and exactly what we change.

Where the published images are:

| | Docker Hub | GitHub's registry |
|---|---|---|
| Name | `<prefix><image>:<version>`, the prefix set for the project (for example `eaexplorer/api:14.8.0`) | `ghcr.io/<owner>/eaexplorer-<image>:<version>` |
| Tags | the version (`14.8.0`), its minor line (`14.8`, the newest patch) and `latest` | the same |

How they are built: [deploy/release/docker-bake.hcl](../deploy/release/docker-bake.hcl), run by
[.github/workflows/publish-images.yml](../.github/workflows/publish-images.yml) when a release is tagged. A developer's
`eax up` still builds the same images from this repository.

## Our images

| Image | Built on (upstream, pinned) | What it is | What we add or change |
|---|---|---|---|
| `api` | `python:3.12-slim` | EA Explorer's API, its background job runner and the first-start setup step | Entirely ours (the `eax` package, the database migrations). The published image also holds what an installation would otherwise read from this repository: the documentation, the help, the release notes, the printed guides (`documents/`), EA Explorer's own document templates, the industry packs and the `deploy` folder. TOGAF's template files are The Open Group's and are never in an image. |
| `web` | `node:22-alpine` to build, `nginxinc/nginx-unprivileged:1.30-alpine` to serve | The screens | Entirely ours (the React application); served by nginx running without root, its packages upgraded and unused modules removed. |
| `backup` | `postgres:17.12-alpine` | Infrastructure backups and restores | Our backup and restore scripts; the image's packages upgraded and `gosu`/`su-exec` removed. |
| `library` | `python:3.12-slim` | The Enterprise library service | Entirely ours. The published image also holds the documentation it serves as the library's EA Explorer folder. |
| `views` | `python:3.12-slim` | The drawn views service | Entirely ours. |
| `ops` | `docker:29-cli` | The operations helper: backups, restores, updates, the test runs, the command centre | Our helper scripts, with Python, git and an SSH client added. |
| `drawio` | `jgraph/drawio:32.6.10` | draw.io, for drawn views | draw.io as published, plus **our plugin** (`eax-plugin.js`) loaded by its page; it acts only inside EA Explorer. |
| `superset` | `apache/superset:6.1.0` | Reports | Superset as published, plus **the database drivers it needs here** (PostgreSQL, sign-in through Keycloak) and **newer versions of packages with known security fixes**; its system packages upgraded. Its settings come from `deploy/superset`, mounted. |
| `jenkins` | `jenkins/jenkins:lts-jdk21` | Jenkins, optional | Jenkins as published, plus **our plugins** (`plugins.txt`), **its settings as code** (`casc.yaml`) and **the pipelines**, made from EA Explorer's command catalogue at start. The plugins are frozen when the image is built, so every installation of a release has the same Jenkins. It runs nothing itself: it asks `eax jenkins agent` on the machine. |
| `eax` | `python:3.12-slim`, with the Docker command from `docker:29-cli` | The `eax` command in a container, so a machine needs only Docker (D976) | What `eax` needs to run: bash, Python, the Docker command with Compose, git, ssh and curl. It runs the deploy folder's own `eax`, mounted at the same path, and reaches the machine's Docker through its socket. `./eax shell` opens a shell in it. |
| `testrunner` | `python:3.12-slim-bookworm` | The self-test (`eax test smoke`, `eax test full`) | Our test code, Chromium for the browser tests, the scanners (pip-audit, bandit, pip-licenses and the others it starts), and in the published image the test data (`testbench/data`). About 1.5 GB; pulled only when a test is run. |
| `eax` | `python:3.12-slim`, with the Docker command and Compose from `docker:29-cli` | The `eax` command in a container (D976): what it needs to run (bash, Python, Docker with Compose, git, ssh, curl), so a machine needs only Docker | Entirely ours: a small start script. The `eax` it runs is the deploy folder's own, mounted at the same path; the machine's Docker is reached through its socket. `./eax <command>` runs one command; `./eax shell` opens a shell in it. A last resort: most people use Jenkins or the deploy page's scripts. |

## Used as their makers publish them

| Image (pinned version) | What it is | Our settings, mounted at start |
|---|---|---|
| `postgres:17-alpine` | The databases | `deploy/postgres/initdb`: the first-start scripts (the databases, roles and extensions) |
| `valkey/valkey:8-alpine` | The job queue and cache (for Documents) | none |
| `nginx:1.30-alpine` | The front door (HTTPS, the routes to each service) | `deploy/proxy/templates` and `deploy/proxy/static` (the maintenance page) |
| `quay.io/keycloak/keycloak:26.0` | Sign-in | `deploy/secrets` (its start script); the realm is made at first start |
| `mayanedms/mayanedms:s4` | Documents | its start script in `deploy/secrets` |
| `jgraph/drawio:32.6.10` | the base of our `drawio` image (above) | |
| `apache/superset:6.1.0` | the base of our `superset` image (above) | |
| `grafana/k6:0.54.0` | Load tests (`eax test performance`) | the test scripts |
| `sonarqube:community`, `sonarsource/sonar-scanner-cli:latest` | Code analysis (`eax test sonar`; developers only) | none |
| `alpine/socat:1.8.0.0` | With an external database on another server (scale-out) | none |

Each of these can be changed in the case file (`EAX_IMAGE_POSTGRES`, `EAX_IMAGE_KEYCLOAK` and the others) when a site
must use another version; the versions above are the ones each release is tested with.

## Keeping this page right

A unit test (`tests/test_d973_published_images.py`) reads the Dockerfiles, the compose file and the bake file, and fails
when this page names a different upstream image or version, leaves one out, or when the published images would hold a
different set of files from those a developer's compose file mounts.
