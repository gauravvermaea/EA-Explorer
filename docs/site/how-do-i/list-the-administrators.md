---
title: List the administrators
summary: Who the administrators are and whether each is enabled.
group: People and access
roles: system-admin
screen: #/admin/setup
---

## Why do this

Knowing who holds administrator rights, and whether each account is enabled, is the first step of any access review or recovery.

Access in EA Explorer is layered so each owner decides for their own part: System Admins for the installation, Model Admins for models, Project Admins for projects. Most people need only a few roles to do their work.

**In TOGAF terms:** The Preliminary phase's architecture capability: who does architecture work and with what authority. Sign-in itself is outside the method. See [[ea-explorer-and-togaf]].

**The goal:** You know who the administrators are.

> **Before you start** You need to run commands on the machine.

## Steps

1. On the machine: `eax access admins`.
