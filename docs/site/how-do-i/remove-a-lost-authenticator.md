---
title: Remove a lost authenticator
summary: A lost phone: the next sign-in sets a new one up.
group: Security
roles: system-admin
screen: #/admin/setup
---

## Why do this

Multi-factor sign-in needs the person's authenticator. When it is lost, removing it from the machine lets them set up a new one at their next sign-in.

Security in EA Explorer is a set of layers: who can reach it, how they prove who they are, what their roles allow, and secrets no one can read. Each layer is set on the screens, and nothing here ever shows a secret's value.

**In TOGAF terms:** Outside the method: this protects the repository and who reaches it. See [[ea-explorer-and-togaf]].

**The goal:** A person who lost their phone can sign in and set up a new one.

> **Before you start** You need to run commands on the machine.

## Steps

1. On the machine: `eax access mfa-off <user name>`.
2. They set a new authenticator up at their next sign-in.
