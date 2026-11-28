# Backups, DR and restores

| | Command | What |
|---|---|---|
| Infrastructure backup | `./eax.sh backup <tag>` | every database, the document files, the certificate and the settings: what rebuilds the machine |
| Application backup | `./eax.sh app-backup <tag>` | every model, every project with its documents, and the organisation part; `--models a,b --projects p` for some |
| One model | `./eax.sh model-backup "<model>" <why>` | the model's own backup |
| One project | `./eax.sh project-backup "<project>" <why>` | with its models and documents |
| Check backups | `./eax.sh check-backup [latest\|all\|<run>\|<file>]` | every zip, its fingerprint and contents; nothing changed |
| List | `./eax.sh backups`, `./eax.sh restores` | |
| Restore the installation | `./eax.sh restore <name> --what full\|app\|app+data\|db\|files` | a backup of the current state first; asks RESTORE |
| Restore the application | `./eax.sh restore-app <run>` | every model and project in it, each over itself |
| Restore one model | `./eax.sh restore-model <run> <file> --new "<name>"` or `--over` | |
| Restore one project | `./eax.sh restore-project <project\|run> <file> --new "<name>"` or `--over` | |

Every backup file is checked as it is written and again before a restore: a damaged or changed file is never restored.
Scheduled backups: Administration > Backups in the screens, or `./eax.sh schedule add ...`.

## Disaster recovery

| | Command |
|---|---|
| **Make a DR pack** (a backup, the settings, this folder, a fingerprint; keep it off the machine, it holds every password) | `./eax.sh dr-pack <folder>` |
| **Recover on a new machine** from a DR pack | on the new machine, in the pack's `dr` folder: `./eax-dr.sh --pack .. --install /opt/ea-explorer` |
| **Test DR** (the automated drill: back up, shut down, rebuild a copy, restore, sign in, compare) | `dr/eax-drill.sh --install <this folder> --dr <new folder> --temp <temp folder>` |

The deploy page's tabs (Back up, Test DR, Do DR, Recover from DR, Restore) write these as scripts for your case, run here
or on a remote server over SSH, or through Jenkins.

## With a managed database

When the database is AWS's or Azure's managed PostgreSQL, the infrastructure backup still takes the databases (with
`pg_dump`, through the network) and the document files; take the cloud's own snapshots as well, as a second copy.
