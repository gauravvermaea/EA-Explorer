---
title: Signing in as a system
summary: Service accounts, tokens, API keys and client certificates: which to use and how to keep them safe.
group: Start here
roles: developer, system-admin
---

## Why systems get their own identities

A connector signed in as a person breaks when that person leaves, does everything that person may do, and makes the
audit trail lie. A **service account** is an identity for one system, with only the rights its job needs, so you can
see what it did and stop it without affecting anyone else. See [[make-a-service-account]].

## The ways to sign in

| Way | Use it for |
| --- | --- |
| Service account API key (Bearer) | Unattended connectors and report refreshes |
| Personal token (Bearer) | Your own scripts, especially when you sign in with single sign-on |
| User name and password (Basic) | OData clients that ask for them |
| Client certificate (port 9443) | Systems that must not hold a shared secret |
| Keycloak access token | Applications that sign people in themselves |

Tokens can be limited to API areas (read or read-write), to some models or projects, and to an end date
([[get-a-token-or-api-key]]). The secret is shown once; keep it in your platform's secret store, never in code.
Revoke it at once if it may have leaked ([[revoke-a-token]]).

## Read next

- [[roles-and-access]]
