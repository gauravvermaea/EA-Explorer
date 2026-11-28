# Deploying EA Explorer {{VERSION}}

The deploy page (https://gauravvermaea.github.io/EA-Explorer-Deploy/) writes a script for your case. This guide says
what the script does, so you can also do it by hand.

## What a machine needs

| | Laptop | Server |
|---|---|---|
| Docker with Compose (`docker compose version`) | Docker Desktop (Windows, macOS) or Docker Engine (Linux) | Docker Engine; your user in the `docker` group |
| Memory | 8 GB or more | 16 GB or more |
| Disk | 20 GB free | 50 GB or more (data and backups) |
| Ports | 80 and 443 free (or others, set in the settings) | 443 (and 80 to redirect) |
| Internet, the first time | the images from GitHub's registry; eax's Python (or use `./eax`, the container) | the same |

## By hand, on this machine

```bash
git clone {{DEPLOY_REPO}}.git ea-explorer && cd ea-explorer
./eax.sh init laptop            # or server: the settings, every password made strong and random
./eax.sh images pull            # this release's images, from {{REGISTRY}}<image>
./eax.sh up --wait-all          # start, and wait until everything answers
./eax.sh logins --admins        # the admin and break-glass passwords, on the screen only
```

Windows (PowerShell): the same with `.\eax` instead of `./eax.sh`.
With only Docker on the machine (no bash tools, no Python download): `./eax <the same commands>` runs them in eax's
container (Linux).

## The settings

`work/eaexplorer.env` holds every setting and every password (readable by its owner only; never commit it, never
send it). The ones a deployment usually changes:

| Setting | What |
|---|---|
| `EAX_HOSTNAME` | the address people use (a server) |
| `EAX_HTTP_PORT`, `EAX_HTTPS_PORT` | the front door's ports |
| `EAX_DATA_ROOT` | one folder for every data folder (a mount point) |
| `EAX_BACKUP_DIR` | where backups go: a local disk, a network share or a cloud file share mounted on the machine |
| `EAX_IMPORT_DIR`, `EAX_EXPORT_DIR`, `EAX_PACKS_DIR` | the import, export and extra packs folders |
| An existing or managed PostgreSQL (AWS RDS, Azure Database for PostgreSQL) | your DBA runs `deploy/external-db/prepare.sql` once (`./eax.sh setup external-db --dba` shows the command), then `./eax.sh setup external-db --host <server> [--port 5432]` tests it and saves it; [backups-and-dr.md](backups-and-dr.md) says what changes for backups |
| `EAX_IMAGES_REGISTRY` | where the images come from (`{{REGISTRY}}` by default; Docker Hub later) |

After a change: `./eax.sh restart`.

## The TOGAF templates (optional, once)

The Open Group's TOGAF template deliverables are not part of EA Explorer: their licence does not allow them to be
shared, so each organisation loads its own copy.

1. Download *The TOGAF Standard, 10th Edition: Template Deliverables* (publication I094):
   <https://publications.opengroup.org/i094>
2. Sign in as a Super Admin, open **Administration > Project library** and press **Upload the TOGAF zip**. Choose the
   zip exactly as you downloaded it; each template is stored unchanged.

Never commit the files or put them in a shared folder. EA Explorer's own templates are ready without them.

## Updating to a newer release

```bash
git pull                         # this repository at the new release
./eax.sh backup before-update    # an infrastructure backup first
./eax.sh images pull
./eax.sh up --wait-all
```

## When something fails

`./eax.sh status` (what runs), `./eax.sh diag` (one file with everything a person helping you needs, passwords masked),
`./eax.sh logs <service>`. Problems: {{CODE_REPO}}/issues
