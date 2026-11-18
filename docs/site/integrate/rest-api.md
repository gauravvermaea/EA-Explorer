---
title: The REST API
summary: Everything the screens do, over HTTP: where it is described, how to sign in, and the conventions.
group: Reading and reporting
roles: developer
---

## Why use it

The REST API is the complete interface: every screen in EA Explorer is built on it, so anything a person can do, a
script can do (within the caller's roles). Use it when the formats and feeds are not enough: reading in detail,
writing with full control, automating admin tasks.

## Where it is described

Every call is described at `https://<your EA Explorer address>/api/docs` (OpenAPI 3), with the document itself at
`/api/openapi.json` for generating a client. You can try calls there with your own sign-in
([[try-the-api-in-the-browser]]).

## Conventions

- Everything is under `/api/v1/`; ids are uuids.
- Writes to a model become uncommitted changes unless the caller may commit; a dry run is offered where a change is big.
- Errors answer a status and a message saying what was wrong and what to do.
- Long work (copies, loads, backups) answers a job id; follow it under `/api/v1/jobs`.

## Signing in

A Keycloak access token, a personal token or a service account's API key, as `Authorization: Bearer ...`; or a client
certificate on port 9443. See [[authentication-for-integrations]].

## Read next

- [[call-the-rest-api]]
