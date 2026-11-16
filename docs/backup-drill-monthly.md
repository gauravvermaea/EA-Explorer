# Restore drill: once a month

A backup is only worth something if it restores. Once a month, prove that the newest backup does, without touching the
installation people use. It takes about an hour. Every step is a command; after each one there is what to check.

On Windows type `.\eax`; on Linux and macOS `./eax`. Below it is written `eax`.

## Part 1: the backups are there and good (on the installation in use, nothing changes)

1. List the backups:

   ```
   eax backups
   ```

   Check: the newest infrastructure backup is less than a day old (the schedule, System Admin › Backups) and shows
   as good.

2. Look at the last restores:

   ```
   eax restores
   ```

   Check: none failed since the last drill. If one did, read it with `eax restore-log <id>`.

## Part 2: one model restored as a new model (on the installation in use, nothing of the original changes)

3. Take an application backup:

   ```
   eax app-backup drill
   ```

4. Restore one model you know from it, **as a new model** (it asks which model and how: choose *as a new model*):

   ```
   eax restore-model
   ```

   Check: the new model opens on the screens with the same number of elements and relationships as the original
   (its Overview tab). Then delete the restored copy (Model admin › the model › Delete).

## Part 3: the whole installation rebuilt from a DR pack, and compared

5. Rehearse a full recovery with the automated drill, on this installation (its folder and data are not touched; the
   DR copy goes into a new folder):

   ```
   .\dr\eax-drill.ps1 -Install <this installation> -Dr <new folder> -Temp <temp folder>
   ```

   Check: it ends with `EA Explorer restore drill PASSED`: every table and file of the DR copy matched the fingerprint
   taken before the backup. Then go back: `eax down` in the DR folder, `eax up` in the installation.

6. Make this month's DR pack and keep it away from the machine:

   ```
   eax dr-pack <folder>
   ```

   Check: it ends with `DR pack ready`. See [Disaster recovery: the DR pack and the DR tool](backup-disaster-recovery.md)
   for what the pack holds and how its checksums and fingerprint prove a recovery.

## Write down

| Date | Backup used | Part 1 | Part 2 | Part 3 | Recovery time | Notes |
| --- | --- | --- | --- | --- | --- | --- |
|  |  | good / failed | good / failed | good / failed | minutes |  |

Keep this table with your operations records; a failed part is fixed before the next backup is trusted.
