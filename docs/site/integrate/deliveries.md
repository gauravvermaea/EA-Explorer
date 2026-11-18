---
title: Deliveries: the folder way in
summary: A source drops a file in a folder; EA Explorer picks it up, checks it and waits for a person to accept it.
group: Connectors
roles: developer, model-admin
---

## Why a folder

The simplest integration needs no API at all: the source writes a file into a folder on a schedule. Most systems can
export a file; most integration tools can copy one. EA Explorer watches the folder.

## How it works

1. A Model Admin sets up an **import source** on the model: its name, its folder, whether its values win over
   people's, and who is told ([[set-up-a-delivery-source]]).
2. Your connector writes a file in a published format into that folder ([[import-formats]]).
3. EA Explorer picks it up and makes a **delivery**: new, changed, kept, unchanged and problem rows.
4. A Committer, Model Sub Admin or Model Admin **accepts** it (committed as their load) or **declines** it with the
   reason ([[accept-a-delivery]], [[decline-a-delivery]]).

From the machine, `eax import` lists and works with deliveries waiting in the import folder.

## Tips

- Write the file under a temporary name and rename it when complete, so a half-written file is never read.
- One file per source per run; send the full set the source is the authority for.
- Problem rows do not stop the rest; they can be corrected on screen ([[correct-a-row-that-failed-to-load]]).

## Read next

- [[push-sources]]
