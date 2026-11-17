# Passwords, keys and certificates

Release 6 (owner, 17 Nov 2026; D742 to D746). How EA Explorer keeps the passwords and keys its services use, how they
change by themselves, and what to do when one needs a person.

## In short

* **No password in a container's settings.** Every password and key reaches the containers that need it as a file of its
  own under `/run/secrets` (Docker secrets), each container only its own. `docker inspect` shows none, and the
  self-test's security suite fails if one ever does. The containers read `work/config.env`: the config file without
  its passwords and keys, written by eax before every start.
* **Two ways for the services to sign in to the database**, chosen at `eax init`:
  * **certificate** (the default on a server): EA Explorer's own certificate authority gives each service its own
    certificate; the database accepts only TLS, and each certificate only for that service's own logins, never the
    superuser;
  * **password** (the default on a laptop, so laptops carry on as before).
* **Everything rotates by itself where it can**: certificates last 30 days and renew at about day 20; passwords and keys
  rotate every 90 days on a server, at a quiet hour. What needs a person is alerted at 30, 14 and 7 days.
* **System Admin › Secrets** shows every one by name (never its value), its age, when it is next due and what needs a
  person, with Rotate now.
* **No key vault, no cloud service** (OpenBao dropped, D744; no platform-specific code, D746).

## Choosing at installation

```
eax init server --certificate       # or --password
```

With neither, eax uses the choice made last time on this machine (so a clean restart does not ask again), else asks
when someone is at the keyboard, else uses passwords on a laptop and certificates on a server. A server's passwords are
made at `init`, strong and random. To change later: `eax certs switch certificate` (or `password`), then `eax restart`.
An installation made before Release 6 stays on passwords until switched.

## Certificate mode

The setup service makes the authority and a certificate for each service at every start, on the machine itself, in the
Docker volume `eax-certs`. Each service sees only its own folder. The authority and the keys are **never in a backup or
a DR pack**: a copy restored elsewhere, or a DR site, makes its own at its first start.

| Who signs in | With | May use |
|---|---|---|
| the API, the job runner, the self-test | its certificate (`api`) | eax_app, eax_migrator, eax_report |
| the library service | `library` | eax_library |
| the drawn views service | `views` | eax_views |
| Keycloak | `keycloak` | keycloak |
| Reports (Superset) | `reports` | superset, eax_report |
| Documents (Mayan EDMS) | `dms` | mayan |
| the SQL window, IT Admin / Super Admin | `console-it` / `console-super` | eax_console_it / eax_console_super |
| backups, maintenance, a database's own creation | the superuser's password, over TLS only | postgres |

If a certificate may have been copied: `eax certs revoke api` refuses it at once (the database checks the revocation
list) and issues a new one. If everything to do with certificates fails, `docker exec` into the db container still
works without any network login, and `eax certs renew --force` makes them all again.

## Rotation

| Kind | How it changes |
|---|---|
| a database login's password | by itself: changed in the database, then the config file, then the services that use it start again (seconds) |
| a sign-in client's secret (Superset, Documents, the API's) | by itself: changed in Keycloak too |
| a key only EA Explorer's services use | by itself |
| the break-glass password, Keycloak's admin, the mail server's, Superset's and Documents' admin, Superset's secret key | **a person**: alerted at 30, 14 and 7 days, with what to do |
| a certificate | by itself, every night if due |
| the certificate authority (about every ten years) | **a person**: `eax certs renew --authority`, alerted months ahead |

The schedules are on System Admin › Commands › Schedules: *Rotate the passwords and keys that are due* (03:17) and
*Renew the certificates that are due* (02:41). A laptop keeps its passwords unless `EAX_ROTATE_ON_LAPTOP=on`.

## The SQL window

**Password mode** (every laptop, and installations from before Release 6): as before, you type a database user and
password; the user is filled in as `eax_app`, and a laptop shows its login (D752).

**Certificate mode**: nobody types a database password (D742). Your EA Explorer role decides: a Super Admin's runs use
the window's Super Admin login (reads and writes; still rolled back unless *Keep the changes* is ticked), an IT Admin's
the IT Admin login (reads only). Two separate logins, so one can never switch to the other's rights.

## Restores and DR

Every restore of the databases and every DR sets each database login's password to the config file in use (R6-D1),
so a backup from before a rotation restores and every service still signs in. In certificate mode the copy makes its
own authority and certificates.

## Commands

`eax secrets` (show, rotate, set, fill, push, pull) and `eax certs` (list, renew, revoke, switch): see `eax help`.
`eax up` runs `eax secrets fill` first: the settings a newer release added are put in the config file, a server's new
passwords made there, so an update needs no hand editing.
