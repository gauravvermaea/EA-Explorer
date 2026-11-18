---
title: Rotate passwords and keys
summary: Change EA Explorer's own passwords and keys, one at a time or all at once, now or on a schedule.
group: Security
roles: system-admin
---

## Why do this

Every password and key in EA Explorer is a file, listed by name and age. Rotating them limits the damage of any leak. See [[running-the-installation]].

Security in EA Explorer is a set of layers: who can reach it, how they prove who they are, what their roles allow, and secrets no one can read. Each layer is set on the screens, and nothing here ever shows a secret's value.

**In TOGAF terms:** Outside the method: this protects the repository and who reaches it. See [[ea-explorer-and-togaf]].

**The goal:** Secrets are fresh, on demand or on a schedule.

> **Before you start** You need the Super Admin or IT Admin role. Rotation is off until you choose it.

## The ways to do it

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

## Each task, one page

1. [Rotate one password or key](../how-do-i/rotate-one-secret.md)
2. [Rotate every password and key](../how-do-i/rotate-everything.md)
3. [Rotate passwords and keys on a schedule](../how-do-i/schedule-rotation.md)
4. [Upload your organisation's certificate](../how-do-i/upload-your-certificate.md)

## Related

- [Get an administrator back in](../guides/get-an-administrator-back-in.md)
