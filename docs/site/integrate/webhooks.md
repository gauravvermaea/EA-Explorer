---
title: Webhooks
summary: EA Explorer tells your system the moment something happens, signed so you know it is genuine.
group: Reading and reporting
roles: developer, system-admin
---

## Why webhooks

Polling an API to see whether anything changed is slow and wasteful. A webhook turns it round: EA Explorer calls your
address when something happens (a notification in a category you choose), so your system can react at once: open a
ticket, post to a channel, start a job.

## What you receive

One plain JSON body per event, with headers:

| Header | What it is |
| --- | --- |
| `X-EAX-Event` | The kind of event |
| `X-EAX-Delivery` | This delivery's id |
| `X-EAX-Signature` | `sha256=` and the HMAC-SHA256 of the body with the webhook's shared secret |

Check the signature with the shared secret before trusting the body. A receiver that fails is retried with back-off,
up to eight times over about two hours, and every delivery is logged.

## Setting one up

System Admins add the address, the categories and the shared secret on **System Admin › System settings › Webhooks**.
See [[receive-webhooks]].

## Read next

- [[overview]]
