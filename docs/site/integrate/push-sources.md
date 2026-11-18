---
title: Push sources and the Python kit
summary: Send records over REST from any language; the Python kit shows the call with pandas.
group: Connectors
roles: developer
---

## Why push

When your connector can make an HTTP call, pushing is the most direct way in: no files, no folders, an answer at once.
What you push still arrives as a delivery for review.

## The call

A push source is set up on the model's **Discovery** tab. Its address takes your records:

```
POST /api/v1/import-sources/<source>/push
Content-Type: application/json

{"applications": [{"name": "Claims portal", "lifecycle_status": "Live"}],
 "servers":      [{"name": "srv-claims-01", "hosts": "Claims portal"}]}
```

Each key is a set (an entity type, mapped on the source's panel); related sets sent together let their links become
relationships. `{"value": [...], "set": "<set>"}` sends one set.

## Signing in

The model's service account, or anyone who may load into the model, with any of: a personal token or a service
account's API key as `Authorization: Bearer ...`; a user name and password as HTTP Basic; a client certificate on the
machine-access port (9443). See [[authentication-for-integrations]].

## The Python kit

The push source's panel has **Push with Python** and **Download the Python kit**: `push_to_eax.py` (reads the CSV files
in a folder with pandas and sends them in one call; `push_dataframe(url, df, username, password)` sends one
DataFrame), `requirements.txt`, a `README.md` with the command for this source, and sample CSVs for every type with a
relationship column the metamodel allows. The script has no checks on purpose: it shows the call for you to build on.
See [[push-data-with-python]].

## Read next

- [[build-a-connector]]
