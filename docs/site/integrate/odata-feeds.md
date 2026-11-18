---
title: OData feeds EA Explorer publishes
summary: Every model as live tables any OData client reads: the addresses, signing in, and what each table holds.
group: Reading and reporting
roles: developer, user
---

## Why OData

OData is an open standard for publishing tables over HTTP. Power BI, Excel and many reporting and integration tools
read it with no code, so publishing the model as OData puts the architecture wherever your organisation already
reports, always current.

## The addresses

| Address | What it is |
| --- | --- |
| `/api/v1/odata/models/<model>/` | The service document: every table of the model |
| `/api/v1/odata/models/<model>/$metadata` | The tables' columns and types |
| `/api/v1/odata/models/<model>/<table>` | One table's rows, paged |
| `/api/v1/odata/governance/` | The Governance Log: decisions, dispensations and reviews |

The model's **Reports › OData** tab shows its own address to copy.

## Signing in

HTTP Basic with your user name and password, or your user name and a personal token as the password (the way for
single sign-on users). A service account's API key works for unattended refreshes. What you may read is what your
roles allow: the feed shows only models and rows you could see on the screens.

## Read next

- [[build-reports-on-odata]]
- [[read-a-model-in-power-bi]]
