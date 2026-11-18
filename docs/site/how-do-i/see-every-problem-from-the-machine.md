---
title: See every problem from the machine
summary: eax status lists every problem now, each with its error code and what to do.
group: Running it
roles: system-admin
screen: #/admin/health
---

## Why do this

When the screens do not open, or you are on the machine anyway, `eax status` tells you everything that is wrong in one place: containers that stopped, parts whose health check fails and alerts that are open, each with its error code and what to do. It works even when the API is down. See [[running-the-installation]].

The installation is built to look after itself as far as it can, and to ask before anything risky. These tasks are the decisions it leaves to you: what to run, when, and how far to trust a change.

**In TOGAF terms:** Outside the method: this keeps the tool that holds the Architecture Repository running. See [[ea-explorer-and-togaf]].

**The goal:** You see every problem and what to do about each.

> **Before you start** You need a command line on the machine EA Explorer runs on, in its folder.

## Steps

1. Run `eax status` (on Windows `.\eax status`). After the containers and the disks it lists the problems, the most serious first.
2. For just the problems, run `eax status problems`; for more about one, run `eax errors <code>`.
3. Do what each says; run `eax status` again to check they have gone.
