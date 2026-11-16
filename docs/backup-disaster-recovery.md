# Disaster recovery: the DR pack and the DR tool

When the machine EA Explorer runs on is lost, you build EA Explorer again on another machine from a **DR pack**: a
backup, the version it was taken with and the config file, together in one folder you keep away from the machine, with
a checksum of every file and a fingerprint of all the data. The **DR tool** (`eax-dr`, in the pack's `dr` folder) does
the rebuild in one command: it checks the pack, downloads that version from GitHub, builds EA Explorer, restores
everything, and proves it by comparing every table and file with the pack's fingerprint.

On Windows type `.\eax`; on Linux and macOS `./eax`. Below it is written `eax`.

## 1. Create a DR pack

1. On the machine EA Explorer runs on, in the EA Explorer folder, make the pack in a new folder (on a disk or share you
   keep away from this machine):

   ```
   eax dr-pack D:\ea-dr-pack-2026-11-16
   ```

   (Linux and macOS: `./eax dr-pack /safe/ea-dr-pack-2026-11-16`.) EA Explorer must be running. It asks nothing:
   - the **maintenance page** goes on and the background pauses, for a few minutes, so nothing changes meanwhile;
   - the **fingerprint**: every table of every database (its rows and a checksum of them) and every file of every
     file set (its checksum);
   - a full **infrastructure backup** (tag `dr-pack`);
   - the maintenance page goes off and the background comes back;
   - the **pack** is written and checked.

   Check: it ends with `DR pack ready` and the version and backup name.

The pack is one folder:

```
ea-dr-pack-2026-11-16/
  backup/20261116T010000Z-dr-pack/   1.1 the backup: every database, the documents, the certificate, persist/, ...
  VERSION.txt                        1.2 the version number, for example 5.6.0
  eaexplorer.env                     1.3 the env file: the config file EA Explorer ran with
  fingerprint.json                   every table and file at the moment of the backup
  dr/                                the DR tool (eax-dr and eax-drill, Windows and Linux)
  RESTORE.txt                        the command to rebuild from this pack
  PACK.sha256                        a checksum of every file above
```

### 1.1 The backup

The backup in `backup/` is a whole infrastructure backup: every database, the document files, the certificate, the
reports' home, the import and export folders, persist/ and the config, with its own checksums (`SHA256SUMS`). It is
also in System Admin › Backups on this machine, tagged `dr-pack`.

### 1.2 The version number

`VERSION.txt` holds the version EA Explorer ran (as the first line of `eax status` says). The DR tool installs exactly
that version, which must be published on https://github.com/gauravvermaea/EA-Explorer/releases (`v5.6.0`).

2. Check: open the Releases page and find the version in `VERSION.txt`.

### 1.3 The env file

`eaexplorer.env` is the config file EA Explorer ran with: the address, every password and key, the settings. Make a new
pack after you change it.

**Keep the pack safe.** The env file holds every password and key of the installation, and the backup holds all its
data. Keep the pack where the people who may rebuild EA Explorer can reach it and nobody else can: an encrypted disk, a
locked share or your organisation's vault for backups. Keep it away from the machine itself, so losing the machine does
not lose the pack. Make a new pack after each upgrade, and as often as you can afford to lose work (your recovery
point).

## 2. Take the DR pack to another server

3. Get the new machine ready:
   - Docker running (Docker Desktop on Windows and macOS; Docker Engine with the compose plugin on Linux);
   - git, if you have it (the DR tool downloads the release's archive without it);
   - access to github.com (the DR tool downloads the release from there);
   - free disk of at least three times the pack's size;
   - ports 80 and 443 free, and the machine's name in DNS as the env file's `EAX_HOSTNAME` says. If the new machine
     has another name, copy the pack's `eaexplorer.env` beside the pack, change `EAX_HOSTNAME` in the copy and give
     it to the DR tool with `-Env <copy>` (`--env` on Linux); the pack's own env file is then not checked or used.

4. Copy the whole pack folder to the new machine, the way you copy anything large and private there: a USB disk, a
   network share, or over SSH:

   ```
   robocopy D:\ea-dr-pack-2026-11-16 \\newserver\c$\ea-dr-pack-2026-11-16 /E      # Windows to Windows
   scp -r /safe/ea-dr-pack-2026-11-16 admin@newserver:/safe/                         # to Linux
   ```

   Check: on the new machine the pack has `backup/`, `VERSION.txt`, `eaexplorer.env`, `fingerprint.json`, `dr/`,
   `RESTORE.txt` and `PACK.sha256`. (The DR tool checks every file against `PACK.sha256` before it does anything.)

5. Decide where EA Explorer goes on the new machine: a new or empty folder, for example `C:\EA-Explorer` or
   `/opt/ea-explorer`.

## 3. Rebuild EA Explorer with the DR tool

6. From the pack's `dr` folder, give the DR tool the pack and the install folder. On Windows (PowerShell):

   ```
   cd D:\ea-dr-pack-2026-11-16\dr
   .\eax-dr.ps1 -Pack .. -Install C:\EA-Explorer
   ```

   On Linux and macOS:

   ```
   cd /safe/ea-dr-pack-2026-11-16/dr
   ./eax-dr.sh --pack .. --install /opt/ea-explorer
   ```

   It asks nothing and stops at the first step that fails, saying why. One step after another:
   - the pack is whole: every file against `PACK.sha256`;
   - checks, nothing touched yet: the backup is whole and not newer than the version; the install folder is new or
      empty; Docker answers; the version is published;
   - the release's code from GitHub into the install folder;
   - the env file and the backup put in place;
   - EA Explorer built and started (the longest step the first time: the images are built);
   - the maintenance page on, everything restored from the backup, EA Explorer started again;
   - **every table and file compared with the pack's fingerprint**: the proof that everything came back as it was
      when the pack was made (the few tables EA Explorer writes by itself, such as sessions and logs, are listed, not
      compared);
   - the maintenance page off, and the smoke test.

   Check: the last line says `EA Explorer DR DONE`. The report is in `<install>/work/dr/dr-<time>/report.md`, with
   the comparison and the recovery time.

7. Sign in on the screens with an account of the old installation, open a model and a project you know, and open one
   of the project's documents.

   Check: they are there as they were when the pack was made.

8. Point your users at the new machine (DNS, or the address you give them), and trust its certificate if it is the
   local one (`eax trust`).

### When the DR tool stops

| It says | What to do |
| --- | --- |
| `... is missing from the pack` / `... does not match its checksum` | The pack was damaged on the way: copy it again from where you keep it. |
| `... is not a published release ... publish it first` | Publish the version in `VERSION.txt` on the Releases page, or give `-Version` with a published one not older than the backup. |
| `the backup is of version X, newer than Y` | Give the backup's own version (or a newer one). |
| `... is not empty` | Give a new or empty install folder. |
| `Docker does not answer` | Start Docker and run the tool again. |
| `Docker already has ... named eaexplorer` | Another EA Explorer runs on this machine: give the copy its own name with `-Project eaexplorer-dr` (`--project` on Linux). |
| `... differ` after the restore | Something did not come back as it was: the report lists each table or file. Keep the pack and look at `<install>/work/logs`. |
| a later step failed | Read the report and `<install>/work/logs`; empty the install folder and run the tool again. |

### Without a pack

The DR tool also takes the parts on their own, when you have a backup but no pack (no fingerprint to compare then):

```
.\eax-dr.ps1 -Backup <backup folder> -Install C:\EA-Explorer -Version 5.6.0 -Env <eaexplorer.env>
./eax-dr.sh --backup <backup folder> --install /opt/ea-explorer --version 5.6.0 --env <eaexplorer.env>
```

## 4. The checksums and the fingerprint, explained

A DR pack proves two different things, each with its own check:

**`PACK.sha256`: the pack arrived whole.** One line for every file of the pack: its SHA-256 checksum (a 64-character
code that changes completely if a single byte of the file changes) and its path. `eax dr-pack` writes it when it makes
the pack; `eax-dr` reads every file of the pack again on the new machine and compares, before it touches anything. A
file damaged or changed on the way, or missing, stops it there. The backup inside the pack carries its own
`SHA256SUMS` too, checked again when the backup is put in place.

**`fingerprint.json`: everything came back.** A picture of all the data at the moment of the backup, taken with the
maintenance page on so nothing changes between the picture and the backup:

- **every table of every database** (the repository, the projects, Keycloak's sign-ins, Superset's reports, the
  documents' database and the rest): how many rows it has, and one checksum over all its rows, worked out the same way
  whatever order the rows are stored in;
- **every file of every file set** (the documents' files, the certificate, the reports' home, the import and export
  folders, persist/) and the config file: each file's SHA-256 checksum.

After the restore, `eax-dr` takes the same picture on the new machine and compares the two, table by table and file by
file. The report says how many tables and files are the same, and names any that differ: a table with fewer rows, a
table with the same rows but other content, a file missing or changed. That is what proves the DR tool did everything:
not that the restore said it finished, but that every row and every file is as it was.

A few tables and files change by themselves while EA Explorer runs (sign-in sessions, logs, the job queue, caches,
heartbeats). They are left out of the comparison and listed in the report as "not compared", so they never make a good
recovery look bad.

The fingerprint holds no data: only counts and checksums. The pack's secrets are in the backup and the env file.

## 5. Rehearse it: eax-drill

A recovery you have never tried is a guess. `eax-drill` (in the same `dr` folder) rehearses one on a running
installation, without touching that installation's folder or data, and proves it with the same fingerprint:

9. Give it the running installation, a new folder for the DR copy and a temp folder. On Windows:

   ```
   .\dr\eax-drill.ps1 -Install C:\Users\you\EA-Explorer -Dr C:\EA-DR\drill1 -Temp C:\EA-DR\temp
   ```

   On Linux and macOS:

   ```
   ./dr/eax-drill.sh --install ~/EA-Explorer --dr /ea-dr/drill1 --temp /ea-dr/temp
   ```

   It asks nothing. One step after another:
   - checks: the installation runs (it stops if not); the DR folder is new and apart from the installation; the
      version is published on GitHub;
   - the smoke test, then a test project, models and content of every kind;
   - the maintenance page on, the fingerprint, a full backup; the test content removed from the installation again,
      the maintenance page off;
   - the installation shut down: its containers removed, its data and images kept;
   - the backup and the env file copied into the temp folder and checked;
   - eax-dr builds the DR copy in the DR folder from GitHub, under its own Docker name (`eaexplorer-dr`, its own data),
      and restores the backup into it;
   - in the DR copy: every table and file compared with the fingerprint, the test content found as it was made, the
      smoke test.

   Check: it ends with `EA Explorer restore drill PASSED`. The report (`<temp>/drill-<time>/report.md`) gives the
   recovery time: from shutting the installation down to the DR copy restored and up.

10. Go back to the installation (the DR copy is left running at the same address):

    ```
    cd C:\EA-DR\drill1; .\eax down
    cd C:\Users\you\EA-Explorer; .\eax up
    ```

    Check: the installation opens as before. Delete the DR folder when you no longer need it (first `eax cleanup --all`
    in it, to remove its Docker data).

Run it once a month ([Restore drill: once a month](backup-drill-monthly.md)), and after each upgrade. The same rebuild
done by hand, step by step, is in [Restore drill: EA Explorer onto a new machine](backup-drill-new-machine.md).

## 6. The commands, in full

Every command asks nothing and stops at the first step that fails, saying why. Each writes a report and a log.

### eax dr-pack: make a DR pack

```
eax dr-pack <folder>
```

| Part | What it is |
| --- | --- |
| `<folder>` | Where the pack goes: a new or empty folder, outside `work/`. On another disk or a share is best. |

Run it in the EA Explorer folder of the running installation (`.\eax` on Windows, `./eax` on Linux and macOS). The
maintenance page is on for the few minutes the fingerprint and the backup take. Writes: `backup/<name>/`,
`VERSION.txt`, `eaexplorer.env`, `fingerprint.json`, `dr/`, `RESTORE.txt`, `PACK.sha256`. The backup also stays in
System Admin › Backups, tagged `dr-pack`.

### eax-dr: rebuild EA Explorer from a pack (or from a backup)

```
.\eax-dr.ps1 -Pack <pack> -Install <folder> [-Env <file>] [-Version <x.y.z>] [-Project <name>] [-Repo <link>]
./eax-dr.sh --pack <pack> --install <folder> [--env <file>] [--version <x.y.z>] [--project <name>] [--repo <link>]

.\eax-dr.ps1 -Backup <backup folder> -Install <folder> -Version <x.y.z> -Env <file> [-Project <name>] [-Repo <link>]
./eax-dr.sh --backup <backup folder> --install <folder> --version <x.y.z> --env <file> [--project <name>] [--repo <link>]
```

| Part (Windows / Linux) | What it is |
| --- | --- |
| `-Pack` / `--pack` | A DR pack's folder. The backup, the version and the env file come from it; every file is checked against `PACK.sha256`; after the restore every table and file is compared with `fingerprint.json`. |
| `-Install` / `--install` | Where EA Explorer goes: a new or empty folder. Always needed. |
| `-Backup` / `--backup` | Without a pack: an infrastructure backup's folder (the one with `manifest.json` and `SHA256SUMS`). |
| `-Version` / `--version` | Without a pack: the version to install, for example `5.6.0`; it must be published on GitHub and not older than the backup. With a pack: only to install another version than `VERSION.txt`. |
| `-Env` / `--env` | Without a pack: the env file (`eaexplorer.env`). With a pack: an edited copy (a new machine's name), used instead of the pack's own. |
| `-Project` / `--project` | Optional. Its own Docker name (containers and data), when another EA Explorer runs on the same machine, for example `eaexplorer-dr`. |
| `-Repo` / `--repo` | Optional. Another GitHub repository to install from; the env file's `EAX_UPDATE_GIT_URL` otherwise. |

Run it from the `dr` folder (the pack's own, or any copy). Report: `<install>/work/dr/dr-<time>/report.md`.

### eax-drill: rehearse a recovery

```
.\eax-drill.ps1 -Install <running installation> -Dr <new folder> -Temp <folder>
./eax-drill.sh --install <running installation> --dr <new folder> --temp <folder>
```

| Part (Windows / Linux) | What it is |
| --- | --- |
| `-Install` / `--install` | The running installation to rehearse on. Its folder and data are never changed; it is shut down during the drill. |
| `-Dr` / `--dr` | A new or empty folder for the DR copy, outside the installation. |
| `-Temp` / `--temp` | A folder for the backup's copy, the fingerprints and the report, outside the installation and the DR folder. |

Report: `<temp>/drill-<time>/report.md`. Go back afterwards: `eax down` in the DR folder, `eax up` in the
installation.
