---
title: Drop a file in the import folder
summary: A system delivers by writing a file into its source's folder.
group: Bringing data in
roles: developer
screen: #/metamodel/{m}/import/deliveries
---

## Why do this

The simplest integration is a folder: the other system writes a file there on a schedule and EA Explorer picks it up as a delivery for review. No API work is needed on either side. See [[bringing-data-in-and-out]].

Every route in ends the same way: what arrives is shown as new, changed, kept and problem rows, and a person decides. That review is what lets you automate feeds without losing control of the model.

**In TOGAF terms:** Supports the content of phases B, C and D (baseline architectures), keeping the Architecture Landscape current from the systems that already know it. See [[ea-explorer-and-togaf]].

**The goal:** Another system delivers by writing a file into a folder.

## Steps

1. Find the source's folder on its panel (Import and export › Deliveries).
2. Write the file there (copy, a scheduled job, a script).
3. It is picked up and waits for review.
