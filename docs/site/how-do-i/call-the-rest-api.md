---
title: Call the REST API
summary: Everything the screens do, from a script, described with OpenAPI.
group: Access for systems
roles: developer
---

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
