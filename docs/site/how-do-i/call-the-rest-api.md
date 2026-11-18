---
title: Call the REST API
summary: Everything the screens do, from a script, described with OpenAPI.
group: Access for systems
roles: developer, platform-developer
screen: /api/docs
---

## Why do this

The REST API is how scripts and other systems work with EA Explorer: everything the screens do, the API does. Every call is described and can be tried, and a token decides what the caller may do. See [[bringing-data-in-and-out]].

Systems that talk to EA Explorer need identities of their own, limited to what they do, so their access can be watched and stopped without affecting people. This is part of keeping integration safe as well as useful.

**In TOGAF terms:** Outside the method: this keeps the repository connected to the systems that feed it, so the Architecture Repository stays current. See [[ea-explorer-and-togaf]].

**The goal:** Another system reads or changes the repository through the API.

> **Before you start** A token or API key (see the related page).

## Steps

1. Open `https://<your EA Explorer address>/api/docs`: every endpoint, what it takes and what it returns.
2. Call it with your token, for example the models you may read:

```
curl -H "Authorization: Bearer <token>" https://<your EA Explorer address>/api/v1/models
```

3. Changes made through the API are yours (or the service account's): uncommitted until committed, and in the change log.

## Related

- [Get a token or an API key](get-a-token-or-api-key.md)
- [Receive webhooks](receive-webhooks.md)
