# Backups

What is backed up, when, where to keep it, and checking it works.

On screen: System Admin > Setup > Backups, where you fill in your values and get every command ready to copy. On the machine: `eax setup backups` with `--set KEY=VALUE` for each value. In Jenkins: the `setup` pipeline with `backups`.

## Your values

| Value | What it is | For example |
|---|---|---|
| `<TAG>` | A word to name the backup (may be left out) | `before-upgrade` |
| `<PACK>` | The folder for the DR pack | `D:/dr-packs` |

## Steps

### 1. A backup now

Every database, the files, the config file; `<TAG>` names it.

Windows (PowerShell):

```
.\eax backup <TAG>
```

Linux or macOS:

```
./eax.sh backup <TAG>
```

### 2. The list

Newest first, with its size and whether it was checked.

Windows (PowerShell):

```
.\eax backups
```

Linux or macOS:

```
./eax.sh backups
```

### 3. Check one restores

A trial restore into scratch copies: nothing live touched.

Windows (PowerShell):

```
.\eax verify
```

Linux or macOS:

```
./eax.sh verify
```

### 4. Off this machine

A DR pack in `<PACK>`, to keep elsewhere (guide: DR site).

Windows (PowerShell):

```
.\eax dr-pack <PACK>
```

Linux or macOS:

```
./eax.sh dr-pack <PACK>
```

### 5. The backup and restore test

Made, backed up, removed, restored, compared.

Windows (PowerShell):

```
.\eax test backup-restore
```

Linux or macOS:

```
./eax.sh test backup-restore
```
