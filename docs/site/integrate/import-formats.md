---
title: The published import formats
summary: The Excel and CSV formats every way in uses: columns, matching, relationships, and what a delivery never does.
group: Connectors
roles: developer, model-admin
---

## Why published formats

A format that is written down and kept stable lets anyone build a connector without talking to the EA Explorer team,
and lets EA Explorer change inside without breaking them. The formats are the same for a person's upload, a folder
delivery and a push.

## Excel

One sheet per entity type, named by the type. Row 1 the column names (`*` marks a required one), row 2 the field codes
(hidden; this is how EA Explorer reads each column), data from row 3.

| Column | Meaning |
| --- | --- |
| `name` | The entity's name: with the type, **how a delivery is matched** |
| `guid`, `display_id` | EA Explorer's keys: match rows in an upload, **ignored in a delivery** |
| `description`, `parent`, `tags` | As on the screens; `parent` by name or id; tags comma-separated |
| attribute codes | Values as text: dates `YYYY-MM-DD`, Yes/No, numbers with a point, a pick list's value; a link `address | note` |
| `delete` | Yes deletes in an upload; **a delivery never deletes** |

A **Relationships** sheet: `source`, `relationship_type` (code or name), `target`, `name`, `delete`; ends by name,
display id, or a new row's provisional id (`NEW-APP-0001`).

## CSV

The same columns, one CSV per sheet, first line the field codes, UTF-8 (Windows-1252 is read too), comma, semicolon
or tab, and a `master.csv` listing the files:

```csv
file,kind,entity_type,entity_type_name
applications.csv,entities,ApplicationComponent,Application Component
relationships.csv,relationships,,
```

## Getting the exact shape for a model

The model's **Import and export**, choose the types, tick **Empty template** ([[download-an-empty-template]]). Or from
code: `POST /api/v1/models/<model>/sheets` with `{"types": [...], "format": "xlsx" or "zip", "blank": true}`.

## Read next

- [[deliveries]]
