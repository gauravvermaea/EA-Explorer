# Setting up an environment: laptop, server, cloud

Every EA Explorer installation has one config file, `work/eaexplorer.env`, made from a template for its kind of
environment. This page gives the commands for each kind. The same is in the README; every command in detail:
[command-line-and-console.md](command-line-and-console.md); deployments step by step: [deployment.md](deployment.md); the first start and every start after, step by step: [starting.md](starting.md).

**`clean-run` and `clean-restart` make it themselves** (they delete the old one first), for a **laptop** unless you
name another kind. To make it on its own, without starting anything, use `init`; it never overwrites a config file
that is there (run `cleanup` first to start again).

**Laptop** (the default; every password is the known laptop one, `eax logins` prints them):

```powershell
.\eax init laptop          # the config file only (the same as .\eax init)
.\eax up                   # build and start
# or both in one step, from scratch:
.\eax clean-run            # = cleanup --all, init laptop, up
```

**Server** (this machine is the server; Linux shown, `.\eax` on Windows Server works the same):

```bash
./eax.sh init server        # the server template; asks for the base folder for all the data (EAX_DATA_ROOT, R5.4)
nano work/eaexplorer.env    # replace EVERY change-me value: EAX_HOSTNAME, the passwords, the certificate settings
./eax.sh check              # Docker, the config file and the compose files are valid; starts nothing
./eax.sh up                 # build and start
# or from scratch in one step (then edit the config file and run ./eax.sh restart):
./eax.sh clean-run server
./eax.sh clean-restart server   # the same while it is running
```

**Another server over SSH, or a new machine in AWS, Azure or DigitalOcean** (the guided deployment: it makes the config
file with every password generated, installs Docker when missing, starts EA Explorer and checks it):

```powershell
.\eax deploy --plan                           # shows every step and command, runs nothing
.\eax deploy                                  # asks: console or web page, then where
.\eax deploy --kind server                    # a server you reach over SSH
.\eax deploy --kind aws                       # also azure, digitalocean (a new machine from your credentials)
```

The same from the screens: the site picker (top left) › **Deploy EA Explorer**; the new site is added to **Sites**
when it is ready. On a machine without EA Explorer yet, `eax-deploy.cmd` (Windows) or `eax-deploy.sh` (Linux, macOS)
downloads the version you choose and then runs `eax deploy`. Every step in detail: [docs/deployment.md](deployment.md).

**A container platform** (Docker Swarm or another orchestrator, no Docker socket and no local disk): start from the
server template, then set `EAX_PLATFORM=managed` (self-tests go to the always-on test runner service) and
`EAX_FILE_STORE=database` (the self-test's files and exports kept in the database), and give the passwords as Docker
secrets if you like (D635):

```bash
./eax.sh init server
# in work/eaexplorer.env: EAX_PLATFORM=managed, EAX_FILE_STORE=database, EAX_BACKUP_DIR=<a mounted volume>
```

**Changing the kind later** (a laptop config to a server one): `init` will not overwrite, so keep a copy, then
`.\eax cleanup` (deletes the work folder, keeps the databases unless `--all`) and `.\eax init server`.

## Where the data lives: local disk or NAS

Every kind of data has its own folder under one base folder, `EAX_DATA_ROOT` (R5.4, D687). EA Explorer does not decide
what is mounted where: you mount a NAS share, another disk or nothing onto each folder, before Docker starts. The rule
of thumb: **the databases on the machine's own fast disk, never on a NAS; the backups off the machine, on a NAS or
another disk; the rest may go either way.** `.\eax folders` shows each folder, whether it is on this machine's own disk
or a mount, and the space free; every `eax up` checks the same before a container starts.

| Folder under `EAX_DATA_ROOT` | Setting | What it holds | Where it should live |
|---|---|---|---|
| `databases` | `EAX_DATA_DIR` | The PostgreSQL server's files: every database in it (EA Explorer's own with all its schemas, Keycloak's, Reports', Documents', the library's and the drawn views') | **Local disk only. Never a NAS.** PostgreSQL needs a disk that writes when it is told to and locks files properly; over NFS or SMB a dropped connection or a delayed write can corrupt the database. On a cloud machine, an attached block disk counts as local |
| `backups` | `EAX_BACKUP_DIR` | Every backup (databases as dumps, files, the config file), and the DR packs made from them | **A NAS or another disk, never the databases' disk.** A backup on the same disk is lost with it. Recommended for every server |
| `documents` | `EAX_DOCS_DIR` | The documents' files (Documents keeps their records in its database) | NAS or local. Large and growing: a NAS suits it. Keep it reachable when EA Explorer starts |
| `logs` | `EAX_LOGS_DIR` | Every container's daily logs and the web log | NAS or local. A NAS keeps them when the machine is lost |
| `imports`, `exports` | `EAX_IMPORT_DIR`, `EAX_EXPORT_DIR` | Files other systems drop for import; files EA Explorer exports | NAS or local. A share people or other systems can reach suits them |
| `certificates` | `EAX_TLS_DIR` | The certificate and its private key | **Local disk.** Small and secret: keep the key on the machine, readable only by its administrators |
| `reports` | `EAX_REPORTS_DIR` | Reports' own files (its secret key, uploads) | **Local disk.** Small, and holds a secret key |

Not under the base folder, and always on the machine's own disk, in the installation folder:

| What | Where | Why local |
|---|---|---|
| The config file | `work/eaexplorer.env` | Holds every password. Every backup and DR pack carries a copy |
| The settings that survive resets, the key vault's keys | `persist/` (`EAX_PERSIST_DIR`) | Small and secret; backed up with the rest |
| The code, the images and Docker's own volumes (`eax-rendered`, `eax-kc-import`) | the installation folder, Docker | Made again from the code and the config file at every start; never backed up |
| Read-only libraries and packs | `library/`, `work/packs` (`EAX_LIBRARY_DIR`, `EAX_PACKS_DIR`) | Read only; either place works |

**Before mounting a NAS share** onto a folder:

* Mount it **before** `eax up` (in `/etc/fstab` on Linux with `_netdev`, or as a service that starts before Docker), so
  the containers never write into the empty folder underneath while the share is missing. `.\eax folders` says
  "mounted at ..." for a folder that is a mount, and "this machine's own disk" for one that is not.
* The containers' users must be able to write to it: on NFS, allow it in the share's settings (root squashing can stop
  the backup container); on SMB, mount it with the user and group IDs the containers use.
* Leave room: backups need space for several sets, and the documents only grow. `.\eax folders` shows the space free.

### By kind of setup

| Setup | Databases | Backups | Documents, logs, imports, exports | Certificates, reports, config file |
|---|---|---|---|---|
| **Laptop** | Docker's volume (the default; on Windows PostgreSQL cannot run on an NTFS folder, so it stays there) | `work/backups`, or `EAX_BACKUP_DIR` on an external disk or a NAS if you keep anything of value | Docker's volumes and `logs/` (the defaults) | the installation folder |
| **One server** | `EAX_DATA_ROOT` on the server's own data disk (not the system disk) | **a NAS share** mounted on `<root>/backups` | local, or NAS shares mounted on their folders | local |
| **A machine in the cloud** | an attached block disk, mounted as `<root>` | the cloud's network file share or object storage synced from `<root>/backups`; at least another disk | the network file share if several people or systems need them, else the attached disk | the attached disk |
| **A container platform** | the platform's block volume for PostgreSQL (one writer only) | a mounted volume (`EAX_BACKUP_DIR`) | `EAX_FILE_STORE=database` keeps the self-test's files and exports in the database; documents and logs on the platform's volumes | the platform's secrets and volumes |

A server example (Linux), with the databases on the data disk and the backups, documents and logs on a NAS:

```bash
# /etc/fstab: the data disk, then the NAS shares mounted onto its folders (before Docker starts)
/dev/sdb1                         /srv/eax              ext4  defaults          0 2
nas01:/export/eax/backups         /srv/eax/backups      nfs   _netdev,hard      0 0
nas01:/export/eax/documents       /srv/eax/documents    nfs   _netdev,hard      0 0
nas01:/export/eax/logs            /srv/eax/logs         nfs   _netdev,hard      0 0

# work/eaexplorer.env
EAX_DATA_ROOT=/srv/eax            # databases, certificates and reports stay on /dev/sdb1

./eax.sh folders                  # databases: this machine's own disk; backups, documents, logs: mounted at ...
./eax.sh up
```

Moving the databases onto a NAS later is never the answer to running out of space: give them a bigger local disk. For
recovery from a lost machine, the backups on the NAS are what count: see
[backup-disaster-recovery.md](backup-disaster-recovery.md).

## Which to use

| You want | Run |
|---|---|
| Try EA Explorer, or develop and test, on your own computer | `.\eax clean-run` (laptop) |
| Test a new version on the laptop, from empty databases | `.\eax clean-restart` |
| Start again the next day, keeping your data | `.\eax run` |
| Install on the server you are on | `./eax.sh init server`, edit the config file, `./eax.sh up` |
| Install on another server, or a new cloud machine | `.\eax deploy` (or Sites › Deploy EA Explorer) |
| Run on Docker Swarm or another platform | `init server`, then `EAX_PLATFORM=managed` and `EAX_FILE_STORE=database` |
