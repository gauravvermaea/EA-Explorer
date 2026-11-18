# Your own database server

EA Explorer on a PostgreSQL server your DBA manages (R6.6.2).

On screen: System Admin > Setup > Your own database server, where you fill in your values and get every command ready to copy. On the machine: `eax setup external-db` with `--set KEY=VALUE` for each value. In Jenkins: the `setup` pipeline with `external-db`.

## Your values

| Value | What it is | For example |
|---|---|---|
| `<DB_HOST>` | Your database server's name | `db.example.org` |
| `<DB_PORT>` | Its port | `5432` |

## Steps

### 1. Your DBA prepares the server

deploy/external-db/prepare.sql: the databases, the logins, their rights.

### 2. Point EA Explorer at it

`<DB_HOST>`, port `<DB_PORT>`: tested before it is saved.

Windows (PowerShell):

```
.\eax setup external-db --host <DB_HOST> --port <DB_PORT>
```

Linux or macOS:

```
./eax.sh setup external-db --host <DB_HOST> --port <DB_PORT>
```

### 3. Start

The db container passes connections through; nothing else changes.

Windows (PowerShell):

```
.\eax restart
```

Linux or macOS:

```
./eax.sh restart
```

### 4. Backups still run

EA Explorer's own backups, over the network; your DBA's on top.

Windows (PowerShell):

```
.\eax backup
```

Linux or macOS:

```
./eax.sh backup
```
