---
title: See the checks a model fails
summary: Every rule an entity breaks, to fix them.
group: Data quality
roles: user, model-admin
screen: #/metamodel/{m}/checks
---

## Why do this

Failing checks lists every rule an entity breaks, so you can fix them in order. Errors block commits, so fixing them first unblocks people's work. See [[data-quality]].

Quality is not a one-off clean-up but a habit: rules catch problems as they are saved, the score shows the trend, and owners fix what is theirs. A model people trust is one they keep using.

**In TOGAF terms:** Supports every ADM phase: the content framework is only useful if its building blocks are complete and correct. See [[ea-explorer-and-togaf]].

**The goal:** You see which entities break which rules.

## Steps

1. Open the model, **Quality › Failing checks**.
2. Open an entity to fix it.
3. Errors block commits; warnings do not.
