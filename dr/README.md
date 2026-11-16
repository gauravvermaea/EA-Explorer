# Disaster recovery: eax-dr and eax-drill

This folder runs on its own: copy it anywhere outside an installation (a USB stick, a share, the machine that is to
hold EA Explorer). Each script has a PowerShell form (Windows) and a bash form (Linux, macOS); both ask nothing.

## eax-dr: build an environment from a DR pack (or a backup)

Make a DR pack on the running installation (`eax dr-pack <folder>`: a backup, the version, the env file, this folder,
`fingerprint.json` and `PACK.sha256`). On the new machine, from the pack's dr folder:

    .\eax-dr.ps1 -Pack .. -Install C:\EA-Explorer
    ./eax-dr.sh --pack .. --install /opt/ea-explorer

It checks every file of the pack, downloads that published release from the EA-Explorer GitHub Releases page (never
the main branch), puts the env file and the backup in place, builds and starts EA Explorer, restores everything with the
maintenance page on, compares every table and file with the pack's fingerprint, and runs the smoke test. Without a pack:
`-Backup <folder> -Version <x.y.z> -Env <file>` (`--backup`, `--version`, `--env`). Report:
`<install>/work/dr/dr-<time>/report.md`. Every option: Documentation › Disaster recovery: the DR pack and the DR tool.

## eax-drill: the restore drill, automated

Proves eax-dr works, on a running installation, without touching its folder. Give it the running installation, a new
folder for the DR copy and a temp folder:

    .\eax-drill.ps1 -Install C:\Users\you\EA-Explorer -Dr C:\EA-DR\drill1 -Temp C:\EA-DR\temp
    ./eax-drill.sh --install ~/EA-Explorer --dr /ea-dr/drill1 --temp /ea-dr/temp

1. Checks, nothing touched: the installation runs (it stops if not); the DR folder is new or empty and apart from it;
   the installation's version is published on GitHub.
2. The smoke test, then a test project, models and content of every kind.
3. The maintenance page on and the background paused, a fingerprint of every table and file, a full backup; the test
   content removed from the installation again and the background back.
4. The installation shut down: its containers removed, its data and images kept.
5. The backup and the env file copied into the temp folder and checked against their checksums.
6. eax-dr builds the DR copy in the DR folder from GitHub, under its own Docker name (`eaexplorer-dr`, its own volumes),
   and restores the backup into it.
7. In the DR copy: every table and file compared with before, the test content found as it was made, the smoke test.

The DR copy is left running at the same address. To go back: `eax down` in the DR folder, then `eax up` in the
installation. The report (`<temp>/drill-<time>/report.md`) gives the recovery time. It can be started from the
installation's own dr folder: it never overwrites the installation; the DR copy always goes into a new folder.
