---
title: Put in your organisation's certificate
summary: Replace the self-made certificate with your organisation's, so browsers trust EA Explorer without a warning.
group: Security
roles: system-admin
---

> **Before you start** You need the Super Admin or IT Admin role, and a certificate covering the name people open
> (for example ea.example.org), reports. and docs. before it, with its private key (no password) and the chain.

## Steps

1. Open **System Admin › Running › Secrets**, **Front door certificate**.
2. Upload the certificate, the chain and the key. It is checked first: the names it covers, its dates, that the key
   matches, that the chain is complete.
3. It is used at once, with no restart and nobody signed out. The one before is kept to undo.

On the machine: `eax certs front install --cert <certificate file> --key <key file> [--chain <chain file>]`;
`eax certs front` shows the one in use; `eax certs front undo` puts the one before back.

## Check it worked

Open EA Explorer in a browser: the padlock shows your organisation's certificate, with no warning.

## If something goes wrong

- **Refused**: the message says why (a name it does not cover, a key that does not match, a missing chain).
- **Expiry**: alerts come 30 days before it ends and on the day.

## Related

- [Install and run: Real certificates](../install/certificates.html), where you give your file names and get the
  commands filled in.
