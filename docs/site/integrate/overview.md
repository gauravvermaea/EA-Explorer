---
title: Integrating with EA Explorer: the map
summary: Every way data gets into and out of EA Explorer, which to choose, and the rules they all share.
group: Start here
roles: developer
---

## Why integrate

An architecture repository is only as current as its sources. The facts it needs (applications, servers, teams,
contracts, costs) already live in other systems: a configuration database, a service management tool, HR, finance. A
good integration brings them in on a schedule so architects work on judgement rather than retyping, and takes the
architecture back out to the reports and tools where decisions are made. See [[bringing-data-in-and-out]].

## The principle: EA Explorer publishes, you connect

EA Explorer is not an ETL tool and does not ship vendor-specific connectors. Instead it **publishes stable formats and
interfaces**, and a connector is whatever reads your source and writes one of them. That keeps EA Explorer simple and
lets you use the tools you already have: a Python script, your integration platform, a scheduled export.

## The ways in

| Way | Best when | Page |
| --- | --- | --- |
| Excel or CSV in the published format | A person or a nightly export produces a file | [[import-formats]] |
| A delivery folder | The source can drop a file somewhere; no API work | [[deliveries]] |
| A push source (REST) | Your connector can make an HTTP call, from Python or anything else | [[push-sources]] |
| An OData source EA Explorer reads | The source already publishes OData | [[odata-sources]] |
| Documents read by AI | The knowledge is in documents | [[discover-the-enterprise-with-ai]] |
| The REST API directly | You need full control, including reads | [[rest-api]] |

## The ways out

| Way | Best when | Page |
| --- | --- | --- |
| OData feeds | Power BI, Excel or any OData client should read live | [[odata-feeds]] |
| Reports on the feeds | You build your own dashboards | [[build-reports-on-odata]] |
| Webhooks | Another system must react when something happens | [[webhooks]] |
| The REST API | Scripts and systems read what they need | [[rest-api]] |
| MCP | An AI agent works with the repository | [[mcp-for-developers]] |

## The rules every integration shares

- **Everything coming in is reviewed** before it counts: new, changed, kept and problem rows, accepted or declined by
  a person. A connector cannot quietly change a model.
- **Rows are matched by type and name**, so a connector needs no EA Explorer ids. A delivery never deletes.
- **Every caller signs in** with its own identity and only the rights it needs: see [[authentication-for-integrations]].
- **Secrets never sit in the database**: a source's sign-in is the name of a setting (`EAX_SOURCE_...`).

## Read next

- [[build-a-connector]]
