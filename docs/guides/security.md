# Security hardening

A checklist for a security review.

On screen: System Admin > Setup > Security hardening, where you fill in your values and get every command ready to copy. On the machine: `eax setup security` with `--set KEY=VALUE` for each value. In Jenkins: the `setup` pipeline with `security`.

## Your values

| Value | What it is | For example |
|---|---|---|
| `<ADDRESS>` | An address or range to let in | `10.20.0.0/16` |

## Steps

### 1. Certificate mode

The services sign in with certificates.

Windows (PowerShell):

```
.\eax certs
```

Linux or macOS:

```
./eax.sh certs
```

### 2. Multi-factor sign-in

System Admin > Security: admins or everyone.

### 3. IP allow-listing

System Admin > Security > Allowed addresses, or from the machine: `<ADDRESS>` let in to the site.

Windows (PowerShell):

```
.\eax allow add site <ADDRESS>
```

Linux or macOS:

```
./eax.sh allow add site <ADDRESS>
```

### 4. Secrets

Every password's age; rotation every 90 days.

Windows (PowerShell):

```
.\eax secrets show
```

Linux or macOS:

```
./eax.sh secrets show
```

### 5. The front door's certificate

The organisation's own (guide: certificates).

### 6. The security test

Scans and attacks.

Windows (PowerShell):

```
.\eax test security
```

Linux or macOS:

```
./eax.sh test security
```
