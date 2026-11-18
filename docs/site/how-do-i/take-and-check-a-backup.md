---
title: Take a backup and check it
summary: A backup of the whole installation now, and a check that it restores, without touching what is live.
group: Backups and recovery
roles: system-admin
---

> **Before you start** You need the Super Admin or IT Admin role.

> **Careful** A backup puts the maintenance page up for a few minutes and waits for background work to finish first, so
> everything in it is from one moment. The screen asks before it starts.

## Steps

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

## Related

- [Restore a backup](restore-a-backup.md)
- [Install and run: Backups](../install/backups.html)
