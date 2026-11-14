# Starting EA Explorer: the first time and every time after

Step by step, for a laptop (Windows, then Linux or macOS) and for a server. Every command in full:
[command-line-and-console.md](command-line-and-console.md); the kinds of environment: [setting-up.md](setting-up.md).

Every password and key is in the config file, `work/eaexplorer.env`. (Release 4 built a key vault, OpenBao, to keep
them instead, R4.19; it is **switched off for now**, owner, 14 Nov 2026: no installation uses it until he decides.)

---

## A laptop (Windows)

### The first time

1. **Install Docker Desktop** and start it. Wait until it says *Engine running*. Check in PowerShell:
   `docker version` must show a *Server* section.
2. **Get EA Explorer**: clone the repository (or `git pull` on `main` if you have it), then open PowerShell in its
   folder.
3. **Start from scratch**:
   ```powershell
   .\eax clean-run
   ```
   This deletes anything from before (the databases, documents and the `work` folder; `persist` is kept), writes the
   config file from the laptop template, builds the images and starts everything. When you see *EA Explorer is ready:
   you can sign in*, the core is up; Reports, Documents and draw.io follow in the background (add `--wait-all` to wait
   for them too).
4. **See the logins** (on a laptop every password is the development one, `P^55w0rd1234&`):
   ```powershell
   .\eax logins
   ```
5. **Optional, once: trust the certificate**, so the browser shows no warning:
   ```powershell
   .\eax trust
   ```
6. **Sign in**: open <https://localhost> and sign in as `eaadmin`.
7. **Check it**:
   ```powershell
   .\eax test smoke     # the quick self-test (System admin > Self-test shows the results)
   ```

### Every time after

```powershell
.\eax run              # (the same as .\eax up) starts everything again; your models, documents and settings are kept
.\eax stop             # stops everything; nothing is deleted
```

### After taking a new version from GitHub

- **Keep your data**: take a backup, pull, then start again; the new images are built and the database is upgraded:
  ```powershell
  .\eax backup before-update
  git pull
  .\eax up
  ```
- **Start again empty** (to test a new version from scratch): `.\eax clean-restart`.

---

## A laptop (Linux or macOS)

The same steps with `./eax.sh` (Docker Engine with Compose v2, or Docker Desktop on macOS):

```bash
./eax.sh clean-run     # the first time
./eax.sh logins        # the passwords
./eax.sh trust         # optional, once
./eax.sh run           # every time after
./eax.sh stop
```

---

## A server

### The first time

1. **Install Docker Engine and Compose v2**, and mount the disks or shares for the data and the backups (the database
   folder `EAX_DATA_DIR`, the documents `EAX_DOCS_DIR`, the backups `EAX_BACKUP_DIR`; Release 5's R5.4 will check
   these before every start).
2. **Get the release** (or use `eax deploy` from another machine, which makes every password for you:
   [deployment.md](deployment.md)).
3. **Make the config file**:
   ```bash
   ./eax.sh init server
   ```
   It asks for the backups folder (a mounted share or volume).
4. **Edit `work/eaexplorer.env`**: replace **every** `change-me` value with a long random password of your own, set
   `EAX_HOSTNAME` (the name people use) and the certificate (`EAX_TLS_DIR` with `tls.crt` and `tls.key`, or leave it
   for a self-signed one). The setup refuses to start while a `change-me` value is left. Keep the file readable by the
   account that runs EA Explorer only.
5. **Check, then start**:
   ```bash
   ./eax.sh check
   ./eax.sh up
   ```
6. **Sign in** at `https://<EAX_HOSTNAME>` as the first admin (`EAX_FIRST_ADMIN_USER`, `eaadmin` unless changed) with
   the `EAX_FIRST_ADMIN_PASSWORD` you set, and change it when asked.
7. **Check it**: `./eax.sh test smoke`. Take the first backup: `./eax.sh backup first`. Optionally keep a copy of the
   passwords in a vault of your own: `./eax.sh secrets push --to file:/etc/eaexplorer/secrets.env` (or `aws:` or
   `azure:`, D504).

### Every time after

```bash
./eax.sh up            # starts again (after a reboot Docker restarts the containers by itself)
./eax.sh stop
./eax.sh update        # a new release: see docs/phase-36-updates.md
```

---

## When something is wrong

- **The setup stops with "still set to the example value"** (a server): a `change-me` value is left in the config file.
- **"... keeps its passwords in OpenBao, but OpenBao is switched off"**: the config file points at the vault
  (`EAX_SECRETS_FROM=openbao:...`). Put the passwords back in the file and remove that line (a dated copy of the file
  is in `work/config-history`).
- Anything else: `.\eax console` (a numbered menu to get it back up), or `.\eax diag` for a full diagnostic log.
