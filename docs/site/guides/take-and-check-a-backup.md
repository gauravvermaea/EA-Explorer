---
title: Take a backup and check it
summary: A backup of the whole installation now, and a check that it restores, without touching what is live.
group: Backups and recovery
roles: system-admin
---

## Why do this

Taking backups is half the job; knowing they restore is the other half. See [[backups-and-recovery]].

Recovery is planned before it is needed: what to protect, how often, how to check it, and how far back each kind of restore reaches. EA Explorer takes a backup of now before any restore, so a restore can itself be undone.

**In TOGAF terms:** Outside the method: this protects the Architecture Repository itself, the record every ADM phase relies on. See [[ea-explorer-and-togaf]].

**The goal:** You have backups and know they restore.

> **Before you start** You need the Super Admin or IT Admin role.

> **Careful** A backup puts the maintenance page up for a few minutes and waits for background work to finish first, so
> everything in it is from one moment. The screen asks before it starts.

## The ways to do it

1. Open **System Admin › Backups and restores › Backups**.
2. **Back up now**, with a tag that says why (for example *before-upgrade*). Or on the machine: `eax backup before-upgrade`.
3. When it is done, it is listed with its size. **Pin** it to keep it for good (pinned backups are never removed).
4. Check it restores: on the machine, `eax verify` restores the newest backup into scratch copies and compares; nothing
   live is touched.

## Check it worked

The backup is listed, newest first, and its log ends without errors. `eax backups` lists them on the machine.

## If something goes wrong

- **It waits a long time at the start**: something in the background is still running; the backup waits up to 30
  minutes, then goes ahead and says what was still busy. System Admin › Running › Jobs shows what is running.
- **Keep a copy off this machine**: a DR pack (`eax dr-pack <folder>`) holds everything needed to rebuild elsewhere.

## Each task, one page

1. [Take a backup now](../how-do-i/back-up-now.md)
2. [Set when backups are taken](../how-do-i/set-a-backup-schedule.md)
3. [Pin a backup](../how-do-i/pin-a-backup.md)
4. [Check a backup restores](../how-do-i/check-a-backup-restores.md)
5. [Make a DR pack](../how-do-i/make-a-dr-pack.md)

## Related

- [Restore a backup](../guides/restore-a-backup.md)
- [Install and run: Backups](../install/backups.html)
