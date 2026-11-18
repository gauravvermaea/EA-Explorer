# A forgotten password or certificate

Getting back in.

On screen: System Admin > Setup > A forgotten password or certificate, where you fill in your values and get every command ready to copy. On the machine: `eax setup forgotten` with `--set KEY=VALUE` for each value. In Jenkins: the `setup` pipeline with `forgotten`.

## Your values

| Value | What it is | For example |
|---|---|---|
| `<USER>` | The administrator's user name | `eaadmin` |

## Steps

### 1. A person's password

Keycloak's Forgot password, or a Keycloak Admin sets one.

### 2. An administrator locked out

`<USER>` gets a temporary password, shown once (changed at the next sign-in).

Windows (PowerShell):

```
.\eax access reset-password <USER>
```

Linux or macOS:

```
./eax.sh access reset-password <USER>
```

### 3. Keycloak is down

The break-glass account (EAX_BREAK_GLASS_PASSWORD).

### 4. A service's password

eax secrets rotate `<KEY>` sets a new one everywhere it is used.

Windows (PowerShell):

```
.\eax secrets show
```

Linux or macOS:

```
./eax.sh secrets show
```

### 5. A certificate

eax certs renew --force makes them all again.

Windows (PowerShell):

```
.\eax certs renew --force
```

Linux or macOS:

```
./eax.sh certs renew --force
```

### 6. Everything else

On the machine, the database answers without a network login: eax psql.
