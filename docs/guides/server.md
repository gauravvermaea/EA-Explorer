# A server

EA Explorer for a team, on a Linux server with Docker.

On screen: System Admin > Setup > A server, where you fill in your values and get every command ready to copy. On the machine: `eax setup server` with `--set KEY=VALUE` for each value. In Jenkins: the `setup` pipeline with `server`.

## Your values

| Value | What it is | For example |
|---|---|---|
| `<HOSTNAME>` | The name people open EA Explorer at | `ea.example.org` |
| `<CERT_FILE>` | The certificate file (PEM) | `C:/certs/ea.crt` |
| `<KEY_FILE>` | Its private key file (PEM, no password) | `C:/certs/ea.key` |

## Steps

### 1. Docker runs

Docker Engine and the compose plugin on the server.

Windows (PowerShell):

```
.\eax check
```

Linux or macOS:

```
./eax.sh check
```

### 2. The config file

Server mode: strong passwords made; certificates chosen by default; the name people open (`<HOSTNAME>`), with DNS records for it, reports.`<HOSTNAME>` and docs.`<HOSTNAME>`.

Windows (PowerShell):

```
.\eax init server --certificate --hostname <HOSTNAME>
```

Linux or macOS:

```
./eax.sh init server --certificate --hostname <HOSTNAME>
```

### 3. The organisation's certificate

Covering `<HOSTNAME>`, reports.`<HOSTNAME>` and docs.`<HOSTNAME>`, from files on this machine: checked, then used at once (or upload it on System Admin > Secrets after the start; guide: certificates).

Windows (PowerShell):

```
.\eax certs front install --cert <CERT_FILE> --key <KEY_FILE>
```

Linux or macOS:

```
./eax.sh certs front install --cert <CERT_FILE> --key <KEY_FILE>
```

### 4. Start

The core, then the rest.

Windows (PowerShell):

```
.\eax up --wait-all
```

Linux or macOS:

```
./eax.sh up --wait-all
```

### 5. Backups

The nightly backup and where it goes (guide: backups).

Windows (PowerShell):

```
.\eax backups
```

Linux or macOS:

```
./eax.sh backups
```

### 6. Check it

The full test, once.

Windows (PowerShell):

```
.\eax test full
```

Linux or macOS:

```
./eax.sh test full
```
