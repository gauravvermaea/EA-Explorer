---
title: OData sources EA Explorer reads
summary: Point EA Explorer at a feed your organisation already publishes; it reads it on a schedule and proposes the changes.
group: Connectors
roles: developer, model-admin
---

## Why

If a source already publishes OData (many configuration and service management tools do), no connector code is
needed: EA Explorer reads the feed's service document or one entity set as JSON, following its pages, and maps the
fields to the model.

## Setting one up

1. On the model's **Import and export › Discovery**, add an **OData feed** source with its address.
2. **Look**: it shows the sets and fields and suggests where each goes; correct and save the mapping.
3. Run it on demand, daily or weekly; each run proposes what changed as a delivery.

See [[read-an-odata-feed-from-another-system]].

## Signing in to the source

Give the **name** of a setting in the config file, `EAX_SOURCE_` and a name (for example
`EAX_SOURCE_INVENTORY=Bearer ...`); its value is sent as the Authorization header. Secrets are never stored in the
database, and no other setting can be sent.

## Reaching it

Addresses on the installation's own network, the machine itself, or a private or link-local network are refused
unless IT lists the host in `EAX_DISCOVERY_ALLOWED_HOSTS` (comma-separated). A configuration database inside your
network is read once it is listed. This stops a source being used to reach things it should not.

## Read next

- [[odata-feeds]]
