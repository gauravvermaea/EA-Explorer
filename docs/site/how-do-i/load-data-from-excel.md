---
title: Load data from Excel
summary: Download a sheet built for the model, fill it in, upload it and check the preview.
group: Working with content
roles: user, model-admin
---

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

- [Change content and commit it](change-content-and-commit.md)
- [Send data with a delivery](send-data-with-a-delivery.md)
