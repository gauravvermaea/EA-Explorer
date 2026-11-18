---
title: Rotate passwords and keys
summary: Change EA Explorer's own passwords and keys, one at a time or all at once, now or on a schedule.
group: Security
roles: system-admin
---

> **Before you start** You need the Super Admin or IT Admin role. Rotation is off until you choose it.

## Steps

1. Open **System Admin › Running › Secrets**. Every password, key and certificate is listed by name (never its value),
   with its age and when it is next due. The yellow box says what needs a person, and why.
2. **Rotate now** beside one changes it at once; the services that use it start again in a few seconds.
3. **Rotate all** changes every one together, behind the maintenance page (it asks first), then asks you to restart.
4. Rotate all **regularly** (monthly or every three months) or **once at a time**, from the same page.

On the machine: `eax secrets show`, `eax secrets rotate <name>`, `eax secrets rotate --all --restart`.

## Check it worked

The age of each rotated one starts again; sign in and open Reports and Documents.

## If something goes wrong

- On Windows, rotation that remakes services runs from PowerShell on the machine (`eax secrets rotate --all --restart`).
- `eax restart` takes down a maintenance page left behind and starts everything again.

## Related

- [Get an administrator back in](get-an-administrator-back-in.md)
