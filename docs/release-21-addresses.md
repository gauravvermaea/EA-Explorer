# Release 21: one installation, several addresses (R21.3)

A planning note for Release 21 (owner, 24 Nov 2026, 15:16 and 15:18: "instead of https://localhost I tried
https://laptop-ea and it is not loading anything ... I want to be able to test the domain names this resolves to or an ip
address"; "Lets add a story there and document how it will be used for installing on remote servers etc"; D911). Not
user documentation (D850): what users read is written in Release 16 from what is built here.

## Today: one name

An installation answers at one name, `EAX_HOSTNAME` (`eax hostname set NAME`, then `eax restart`): `localhost` on a
laptop, the server's name on a server. Four parts depend on it:

| Part | Where | What it holds today |
|---|---|---|
| The site certificate | `services/api/eax/setup/tls.py` | `EAX_HOSTNAME`, `reports.` and `docs.` of it, `localhost`; no IP address |
| The installation's own certificate authority | same file | may sign only `EAX_HOSTNAME`, `localhost` and `127.0.0.1` (name constraints) |
| Keycloak | `docker-compose.yml` (`KC_HOSTNAME`) | fixed at `https://EAX_HOSTNAME:PORT/auth`: sign-in sends people there |
| The realm's sign-in clients | `deploy/keycloak/realm-eaexplorer.json.tmpl` | come back only to `EAX_PUBLIC_URL` |
| The API's check of a token | `services/api/eax/auth.py` | one issuer: the public Keycloak address |

nginx is not in the way: the main site is the default server and answers any name; the screens build their addresses from
the one the browser used. Reports and Documents are on `reports.NAME` and `docs.NAME`, which an IP address cannot have.

What a second name does today: the certificate is refused (and the authority may not sign it), and sign-in goes back to
the first name or fails with "Invalid redirect_uri". On Windows the machine's own name often resolves to an IPv6 or a
Wi-Fi address first; Docker Desktop publishes 443 on the IPv4 ones: a browser can wait with nothing shown.

## The direction to think through first (owner, 24 Nov 2026, 15:30)

"how where we install should not deal with how we resolve, can we have nginx work as a reverse proxy and just forwards
requests?" The principle: the installation does not know the names it is reached at; only the front door (nginx) does,
and everything behind it works from what nginx forwards (X-Forwarded-Host, -Proto, -Port), trusted from nginx only.

- **The screens**: already so (they build addresses from the browser's).
- **The API**: already reads the forwarded headers; the token check would take the realm's tokens at whatever host nginx
  forwarded (issuer = that host's /auth/realms/<realm>), still checked against the realm's keys and audience.
- **Keycloak**: no fixed hostname; the name from nginx's forwarded headers (hostname v2); sign-in clients that come
  back to "this site, whatever its name" (relative addresses), not a list.
- **Reports and Documents**: under paths on the same address (`/reports/`, `/docs/`), not `reports.` and `docs.`
  names, so they need no DNS of their own and work at an IP address. The largest part: Superset and Mayan under a path.
- **What cannot be name-free**: (1) the certificate, which the browser checks against the name it typed: nginx's
  certificate lists the names (the one setting left at the door), or TLS ends at the organisation's own load balancer
  or proxy in front, or a public certificate is fetched for a public name (ACME); (2) links that leave the site (mail,
  alerts, exports): one public address for those only, never for serving.

Then the "list of names" below shrinks to the certificate's names at the door. To choose between the two when Release 21
starts; the hosts-file testing below serves both.

## What R21.3 builds (the list-of-names approach, if the direction above is not taken)

One primary name, as today, and a list of other names and IP addresses the same installation answers at:

- `EAX_HOSTNAME`: the primary name (links in mail, alerts, the API's own pages, DR).
- `EAX_OTHER_NAMES`: other names and IP addresses, comma separated (`laptop-ea,192.168.1.40,ea.internal`).
- `eax hostname add NAME|IP`, `eax hostname remove NAME|IP`, `eax hostname` (lists them); each takes a dated copy of the
  config file first, then asks for `eax restart`. In the screens: System Admin > Settings > System settings, Super Admin.

What each part does with the list:

1. **The certificate** names every one of them (DNS names and IP addresses), with `reports.` and `docs.` of each DNS name.
2. **The authority's name constraints** take the list too. An authority made before keeps its constraints, so adding a
   name makes a new authority, to be trusted again once on each computer that opens EA Explorer (said by the command).
   A certificate of the organisation's own (`eax certs use`) is unchanged: it must cover the names itself.
3. **Keycloak** takes the address the browser used (hostname v2, no fixed `KC_HOSTNAME`, the name taken from the proxy's
   forwarded headers, which only the proxy may set), so sign-in stays on the name it was opened at.
4. **The realm** accepts every name in the list as a place to come back to after sign-in and sign-out.
5. **The API** accepts tokens issued at any name in the list (one issuer each), and no other.
6. **Reports and Documents** at an IP address: on their own ports (`https://IP:8443` Reports, `https://IP:8444`
   Documents), as an IP address has no `reports.` beside it.
7. **The allow list** (System Admin > Security) is unchanged: a name is not a way round it.

## How it is used

- **Testing on a laptop by its machine name or IP address** (the owner's case): `eax hostname add laptop-ea` and
  `eax hostname add 192.168.1.40`, `eax restart`, trust the new authority once; `https://laptop-ea` and
  `https://192.168.1.40` then work beside `https://localhost`. Another computer on the network also needs the firewall
  open for 443 (said by the command on Windows).
- **A remote server with one public name**: as today, `EAX_HOSTNAME=ea.example.org`; nothing else.
- **A remote server with a public and an internal name** (people outside at `ea.example.org`, inside at `ea.corp.local`):
  the primary is the public name; the internal one is added. Each needs a DNS record; the certificate covers both (the
  organisation's own certificate, or the installation's authority trusted inside).
- **Behind a load balancer or another proxy**: the name people use is the primary; the load balancer's own name is added
  only when people open it; the forwarded headers are taken only from the addresses named as trusted proxies.
- **Distributed servers (R21.2)**: each service is reached by the names in the list from the others; the primary is the
  one name people use; the servers' own names are added for the services that call each other across machines.
- **Disaster recovery**: unchanged: the DR site answers at the same primary name once DNS points there (bookmarks keep
  working); a DR site's own name can be added for checking it before the switch.
- **An IP address only, in a lab with no DNS**: the IP is the primary or added; Reports and Documents on their ports.

## Testing it with a hosts file (owner, 24 Nov 2026, 15:19: "we will simulate by having hosts file")

The names a server would have in DNS are simulated on the laptop in its hosts file
(`C:\Windows\System32\drivers\etc\hosts`, edited as administrator; `/etc/hosts` on Linux and macOS), each pointing at
this machine. A hosts file has no wildcards, so `reports.` and `docs.` of each name get a line of their own:

```
127.0.0.1  ea.example.test  reports.ea.example.test  docs.ea.example.test     # the "public" name
127.0.0.1  ea.corp.test     reports.ea.corp.test     docs.ea.corp.test        # the "internal" name
```

Then `eax hostname set ea.example.test`, `eax hostname add ea.corp.test`, `eax hostname add laptop-ea` and
`eax hostname add <the laptop's IPv4 address>`, `eax restart`, and the new authority trusted once. Each name is opened,
signed in at and signed out of; Reports and Documents are opened at each. `.test` names are kept for testing and never
reach the internet. A name left out of the hosts file is not found: the hosts file is the DNS the test checks against.
The self-test's journey for R21.3 takes its names from an `EAX_TEST_NAMES` setting, so the same journey runs against the
hosts file on a laptop and against real DNS on a server.

## Tests (built with it)

Unit: the certificate's names and IP addresses; the authority's constraints; the realm's addresses; the API accepting
a token from each listed issuer and refusing any other; `eax hostname add|remove` in every form (eax.ps1, eax.sh, eaxpy,
help.txt, D331). The full test: a journey that signs in at a second name and an IP address and opens Reports at the IP
address's port.

## To settle with the owner when Release 21 starts

- The setting's name and the command (`EAX_OTHER_NAMES`, `eax hostname add`), and whether the screens may change it.
- Reports and Documents at an IP address: their own ports, or paths (`/reports/`) for every name.
- Whether a laptop adds its machine name and its addresses by itself at `init`.
