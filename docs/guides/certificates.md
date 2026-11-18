# Real certificates

The front door's certificate: your organisation's, uploaded.

On screen: System Admin > Setup > Real certificates, where you fill in your values and get every command ready to copy. On the machine: `eax setup certificates` with `--set KEY=VALUE` for each value. In Jenkins: the `setup` pipeline with `certificates`.

## Your values

| Value | What it is | For example |
|---|---|---|
| `<HOSTNAME>` | The name people open EA Explorer at | `ea.example.org` |
| `<CERT_FILE>` | The certificate file (PEM) | `C:/certs/ea.crt` |
| `<KEY_FILE>` | Its private key file (PEM, no password) | `C:/certs/ea.key` |
| `<CHAIN_FILE>` | The chain file (the issuers' certificates) (may be left out) | `C:/certs/chain.crt` |

## Steps

### 1. Ask for one

Covering `<HOSTNAME>`, reports.`<HOSTNAME>` and docs.`<HOSTNAME>`; with its private key (no password) and the chain.

### 2. Put it in

From files on this machine (or upload it on System Admin > Secrets > Front door certificate): checked, used at once, no restart, the one before kept.

Windows (PowerShell):

```
.\eax certs front install --cert <CERT_FILE> --key <KEY_FILE> --chain <CHAIN_FILE>
```

Linux or macOS:

```
./eax.sh certs front install --cert <CERT_FILE> --key <KEY_FILE> --chain <CHAIN_FILE>
```

### 3. Check it

The names it covers, who issued it, when it ends; undo puts the one before back.

Windows (PowerShell):

```
.\eax certs front
```

Linux or macOS:

```
./eax.sh certs front
```

### 4. Expiry

Alerts 30 days before and on the day.

### 5. Laptops trust your authority

Company laptops trust your organisation's authority already, or IT adds it.
