---
title: Build a connector
summary: The pattern for a connector from any source system: read, map, write a published format or push, schedule, watch.
group: Connectors
roles: developer
---

## What a connector is here

A connector is a small program (or a job in your integration platform) that reads a source system and hands EA
Explorer what it found in a published shape. EA Explorer does the rest: matching, checking against the metamodel,
showing the changes for review, loading. Your connector does not need to know EA Explorer's database or ids.

## The pattern

1. **Agree the scope with the Model Admin**: which entity types and attributes the source is the authority for, and
   whether its values should win over people's edits (a setting of the source).
2. **Get the shape**: download the empty template for those types ([[download-an-empty-template]]), or the push
   source's sample files from the Python kit. The column codes are your target.
3. **Read the source**: its API, a database view, an export. Keep the read simple and repeatable.
4. **Map**: one row per entity, `name` as the key, attribute codes as columns, values as text (dates `YYYY-MM-DD`,
   Yes/No, a pick list's value). Relationships as `source`, `relationship_type`, `target`, by name. See [[import-formats]].
5. **Deliver**: write the file into the delivery folder ([[deliveries]]), or push it over REST ([[push-sources]]).
6. **Schedule it**: the operating system's scheduler, your integration platform, `eax schedule`, or a Jenkins pipeline.
7. **Watch it**: each delivery has a log and a review; problem rows can be corrected on screen; a webhook can tell you
   when a delivery is accepted or declined ([[webhooks]]).

## Make it safe to run again

Deliveries are matched by type and name, so sending the same data twice changes nothing; only real differences are
shown. Send the whole set the source is the authority for each time rather than a list of changes: missing rows are
shown as "no longer delivered" for a person to decide, never deleted.

## Examples

| Source | Types | Usual way |
| --- | --- | --- |
| Configuration database | Node, System Software, Device | OData source, or a nightly CSV into the folder |
| Service management tool | Application Component, Application Service | Push from Python |
| HR system | Business Actor, Business Role | Nightly export in the Excel format |
| Finance | cost attributes on applications | CSV of name and cost |
| Cloud accounts | Node, Technology Service | Push from a script using the cloud's own CLI |

## Read next

- [[push-sources]]
- [[authentication-for-integrations]]
