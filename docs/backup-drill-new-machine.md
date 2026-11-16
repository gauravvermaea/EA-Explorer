# Restore drill: EA Explorer onto a new machine

When the machine EA Explorer runs on is lost, this is how you bring it back on another one from a backup, by hand, step
by step. The DR tool does all of it in one command from a DR pack (`eax dr-pack` makes one; `eax-dr -Pack` rebuilds
from it and compares every table and file with the pack's fingerprint): see
[Disaster recovery: the DR pack and the DR tool](backup-disaster-recovery.md). Do it once
as a drill before you need it, so you know it works and how long it takes. Every step is a command; after each one
there is what to check before you go on.

On Windows type `.\eax`; on Linux and macOS `./eax`. Below it is written `eax`.

## What you need

- The newest infrastructure backup: a folder under `work/backups/infrastructure/` on the old machine (or a copy of it
  wherever you keep your backups).
- The old installation's config file, `work/eaexplorer.env`, and its `persist/` folder (they hold the passwords, the
  schedules and the settings). A backup holds the config file too; keep a copy of both outside the machine anyway.
- The new machine with Docker running and the same EA Explorer version as the backup (the backup says which, in its
  `versions.json`).
- About twice the backup's size free on disk.

## On the old machine (when it still runs)

1. Take a fresh backup and give it a tag you will recognise:

   ```
   eax backup drill
   ```

   Check: `eax backups drill` lists it as good, with its size.

2. Copy the backup's folder, `work/eaexplorer.env` and `persist/` to where the new machine can reach them (a share,
   a disk, cloud storage).

## On the new machine

3. Get the same version of EA Explorer:

   ```
   git clone https://github.com/gauravvermaea/EA-Explorer.git EA-Explorer
   cd EA-Explorer
   git checkout v5.6.0
   ```

   Use the version the backup was taken with. Check: the first line of `eax status` names it.

4. Make the work folders:

   ```
   eax init laptop
   ```

   (or `eax init server` on a server). Check: `work/eaexplorer.env` exists.

5. Put the old config file and `persist/` in place: copy `eaexplorer.env` over `work/eaexplorer.env`, and the
   `persist/` folder into the installation's folder.

   Check: `eax check` says the config is valid.

6. Put the backup in place: copy the backup's folder into `work/backups/infrastructure/`.

   Check: `eax backups` lists it.

7. Start EA Explorer once, so its containers and databases exist:

   ```
   eax up --wait-all
   ```

   Check: `eax status` shows every container up.

8. Restore everything from the backup:

   ```
   eax restore drill --what full --yes
   ```

   It takes a backup of the empty installation first, then puts every database, the document files, the certificate
   and the config back. Check: `eax restores` shows it finished; `eax restore-log <id>` has its whole log.

9. Start again so every service reads what was restored:

   ```
   eax up --wait-all
   ```

## Check that it works

10. Sign in on the screens with an account of the old installation.
11. Open a model and a project you know; open a document of the project (Documents).
12. Open a report dashboard (Reports).
13. Run the smoke test:

    ```
    eax test smoke
    ```

    Check: it passes.

## Write down

- How long it took from step 3 to step 13: your **recovery time**.
- When the backup was taken, against when the old machine stopped: what was lost, your **recovery point**.
- Anything that did not work, and what you did about it.

Then tidy up: `eax delete-backup <name>` for the backup the restore took of the empty installation, if you do not
need it.
