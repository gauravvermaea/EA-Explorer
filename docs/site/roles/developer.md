---
title: What EA Explorer has for developers
summary: You bring data in and take it out: the REST API, the OData feed, the published import formats, deliveries, push sources with Python, webhooks and MCP.
---

## Who this is for

People who connect EA Explorer to other systems: they write the scripts and ETL jobs that send data in, read models out
for reports, receive EA Explorer's events, or build on its API. EA Explorer is not an ETL tool itself: it publishes its
formats and feeds, and your jobs read and write them.

## What you have

| Way in or out | Where | What it gives you |
|---|---|---|
| The REST API | `/api/v1/...`, described at `/api/docs` (OpenAPI) | Everything the screens do |
| Machine access | System Admin › Machine access; Me › My tokens and keys | Tokens, API keys and client certificates for people and service accounts, read or read-write per area, for some models or all, with an expiry |
| The OData feed | A model's Reports › OData | Every entity type as a table, read only, for Power BI, Excel or any OData client |
| Import formats | A model's Import and export | The Excel format and the CSV format (one CSV per sheet with `master.csv`), empty templates made for each model |
| Deliveries | A model's Import and export › Deliveries | A source per system: files dropped in its folder, sent to the API, or uploaded; previewed and accepted by a Committer |
| Discovery sources | A model's Import and export › Discovery | An OData feed EA Explorer reads, a push endpoint your system sends to (with a Python kit), or documents read by AI |
| Webhooks | System Admin › Settings › System settings, Webhooks (IT and Super Admins) | Signed messages to your systems when something happens (a commit, a metamodel change, a request, a model) |
| MCP | AI (MCP) › Connect your AI assistant | About 140 tools and guided prompts for an AI assistant, as the person signed in |
| Model packages | Model Admin › Wizards › Download | A whole model as a zip or Excel file (without data, with data, or with its history), to move between installations or put on git |

## How it is put together

- **Signing in**: a person signs in through Keycloak; a system uses a **token** or **API key** (sent as
  `Authorization: Bearer ...`) or a **client certificate** on the machine-access port. Each is limited to the areas and
  models you choose, expires, can be revoked, and every call is in the change log.
- **Data goes in as a delivery or a load**: matched by entity type and name; a delivery only adds and changes (it never
  deletes), and keeps EA Explorer's values unless its source's values are set to win; nothing reaches the model until a
  Committer accepts it.
- **Data comes out** through the OData feed (read only, with the reader's permissions), the REST API, Excel and CSV
  exports, and model packages.
- **IDs**: every entity has a GUID and a display ID (for example APP-0012). Deliveries match by name, so your system
  does not need EA Explorer's IDs.
- **Permissions** always apply: a token or a person reads only what they may read, and changes only what they may
  change.

## Where to go next

- The tasks below, one page each.
- The API's own pages in your installation: `/api/docs`.
- The standards: [OData, OpenAPI and MCP](../further-reading.md).
