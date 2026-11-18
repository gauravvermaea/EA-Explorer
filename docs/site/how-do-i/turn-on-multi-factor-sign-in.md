---
title: Turn on multi-factor sign-in
summary: Ask admins, or everyone, for a one-time code from an authenticator app when they sign in.
group: Security
roles: system-admin
---

> **Before you start** You need the Super Admin or IT Admin role. People need an authenticator app on their phone.

## Steps

1. Open **System Admin › Security**.
2. Under **Multi-factor sign-in**, choose **Admins** (the Super Admins and IT Admins) or **Everyone**. **Off** is the
   default.
3. Save. It applies at once: the people it covers set up their authenticator at their next sign-in.

## Check it worked

Sign out and in: after the password, EA Explorer asks for the code (the first time, it shows a QR code to scan).

## If something goes wrong

- **Someone lost their phone**: on System Admin › Security, reset their authenticator; they set up a new one at the
  next sign-in. An administrator locked out can be helped from the machine: `eax access mfa-off <user name>`.

## Related

- [Get an administrator back in](get-an-administrator-back-in.md)
- [Limit who can reach EA Explorer](limit-who-can-reach-ea-explorer.md)
