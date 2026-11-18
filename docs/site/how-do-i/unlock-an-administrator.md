---
title: Unlock an administrator
summary: After too many wrong passwords.
group: People and access
roles: system-admin
screen: #/admin/setup
---

## Why do this

Too many wrong passwords lock an account to stop guessing. Unlocking from the machine lets a legitimate administrator back in at once.

Access in EA Explorer is layered so each owner decides for their own part: System Admins for the installation, Model Admins for models, Project Admins for projects. Most people need only a few roles to do their work.

**In TOGAF terms:** The Preliminary phase's architecture capability: who does architecture work and with what authority. Sign-in itself is outside the method. See [[ea-explorer-and-togaf]].

**The goal:** An administrator locked out after wrong passwords can sign in again.

> **Before you start** You need to run commands on the machine.

## Steps

1. On the machine: `eax access unlock <user name>`.
2. They can sign in again at once.
