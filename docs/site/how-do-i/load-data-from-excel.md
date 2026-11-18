---
title: Load data from Excel
summary: Download a sheet built for the model, fill it in, upload it and check the preview.
group: Working with content
roles: user, model-admin
screen: #/metamodel/{m}/import
---

## Why do this

Excel is how most architecture data starts. Loading a sheet with the model's own columns and drop-downs brings it in with a preview of new, changed and problem rows, and the whole load can be undone. See [[bringing-data-in-and-out]].

Content work is the everyday heart of architecture: recording what exists and what should, and how it all connects. EA Explorer checks it against the metamodel as you go and keeps it as your change until it is reviewed.

**In TOGAF terms:** Phases B, C and D: recording the building blocks and relationships of the baseline and target architectures. See [[ea-explorer-and-togaf]].

**The goal:** Many entities and relationships go in at once from a sheet.

> **Before you start** You need the Architect role (or higher) on the model.

## Steps

1. Open the model, **Import and export** (or Model Admin › Wizards, **Load data**).
2. Choose the entity types and download the sheet: one sheet per type with drop-downs, and a Relationships sheet.
3. Fill it in. Leave the IDs as they are for rows already there; new rows need a name.
4. Upload it. A preview shows the new, changed and problem rows before anything loads.
5. Load: the rows become your uncommitted changes. Commit them.

## If something goes wrong

- The preview names each problem row and why (a value not in the pick list, a relationship the metamodel does not allow).
- Undo a whole load on its load page.

## Related

- [Change content and commit it](../guides/change-content-and-commit.md)
- [Send data with a delivery](../guides/send-data-with-a-delivery.md)
