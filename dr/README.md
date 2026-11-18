# Disaster recovery: eax-dr and eax-drill

This folder runs on its own: copy it anywhere outside an installation (a USB stick, a share, the machine that is to
hold EA Explorer). Each script has a PowerShell form (Windows) and a bash form (Linux, macOS); both ask nothing.

## eax-dr: build an environment from a DR pack (or a backup)

Make a DR pack on the running installation (`eax dr-pack <folder>`: a backup, the version, the env file, the code
that runs there (`code/`, with `CODE.sha256`), this folder, `fingerprint.json` and `PACK.sha256`). On the new machine, from the pack's dr folder:

    .\eax-dr -Pack .. -Install C:\EA-Explorer
    ./eax-dr.sh --pack .. --install /opt/ea-explorer

It checks every file of the pack, copies the pack's code into the install folder (no GitHub needed; `-GitHub` takes
the published release from GitHub instead), puts the env file and the backup in place, builds and starts EA Explorer, restores everything with the
maintenance page on, compares every table and file with the pack's fingerprint, and runs the smoke test. The new machine
needs Docker and what building the images downloads (Docker Hub, the Python and Node packages), not GitHub. Without a
pack: `-Backup <folder> -Env <file> -Code <folder>` (a copy of the code `eax drill code <folder>` made), or
`-Version <x.y.z>` instead of `-Code` to take the code from GitHub (`--backup`, `--env`, `--code`, `--version`). Report:
`<install>/work/dr/dr-<time>/report.md`. Every option: Documentation › Disaster recovery: the DR pack and the DR tool.

## eax-drill: the restore drill, automated

Proves eax-dr works, on a running installation, without touching its folder. Give it the running installation, a new
folder for the DR copy and a temp folder:

    .\eax-drill -Install C:\Users\you\EA-Explorer -Dr C:\EA-DR\drill1 -Temp C:\EA-DR\temp
    ./eax-drill.sh --install ~/EA-Explorer --dr /ea-dr/drill1 --temp /ea-dr/temp

1. Checks, nothing touched: the installation runs (it stops if not); the DR and temp folders are apart from it and hold
   nothing but an earlier drill's leftovers, which are then removed (the earlier DR copy from Docker too) and the
   folders made. A folder holding anything else is refused, never deleted. The pre-flight, in seconds: enough free
   disk for the backup, its copy and the DR copy (too little stops it); a container still starting or the background
   busy is a warning.
2. The maintenance page on and the background paused; the key items counted (models, elements, relationships,
   commits, projects, documents, people). No test content is made.
3. A full backup, copied straight out of EA Explorer into the temp folder while it still runs, with the env file and
   the installation's code, and checked against their checksums, as a DR pack holds them.
4. The background back; the installation shut down: its containers removed, its data and images kept.
5. eax-dr builds the DR copy in the DR folder from that code (no GitHub), under its own Docker name (`eaexplorer-dr`, its own volumes),
   and restores the backup into it.
6. In the DR copy: **a real sign-in** (Keycloak signs its admin in and counts EA Explorer's people; the API answers), then
   the key items compared with before and the rest of the DR copy started. The smoke test only with `-Smoke`.

7. Then the DR copy is **left running** for you to test, at the address your installation uses, and your installation
   stays stopped (they share the ports). Back to your installation: `.\eax stop` in the DR folder, `.\eax up` in the
   installation. The next drill removes the DR copy at its start (and starts the installation if it is stopped). The
   drill's backup is kept (pinned): `eax drill delete-backup <name>` when done. The temp folder is deleted. When the
   drill fails before the DR copy is built, the installation is started again.

**Failures and warnings** (owner, 18 Nov 2026, 07:12: "this will be used in critical failure so things need to work";
"unless the actual migration fails dont fail test. If we can login into the new instance we are good"): the drill
**fails** only when the restore cannot be done or nobody can sign in: the checks before anything is touched (too
little disk, the installation down), the backup and its copy, shutting down, eax-dr (build and restore) and the
sign-in. Everything else is a **warning**: noted, the drill carries on, and it ends `PASSED with N warning(s)`: the
maintenance page, the background, the key items counted and compared, the rest of the DR copy starting, the smoke
test. eax-dr itself works the same way in a real disaster. A failure leaves `diagnostics/` beside the report.

The report stays in the installation (`work/tests/drill-<time>/report.md`) and gives the recovery time. It can be started from the
installation's own dr folder: it never overwrites the installation; the DR copy always goes into a new folder.
