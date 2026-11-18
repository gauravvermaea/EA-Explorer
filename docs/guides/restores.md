# Restores

A model, a project, a part or everything put back.

On screen: System Admin > Setup > Restores, where you fill in your values and get every command ready to copy. On the machine: `eax setup restores` with `--set KEY=VALUE` for each value. In Jenkins: the `setup` pipeline with `restores`.

## Your values

| Value | What it is | For example |
|---|---|---|
| `<BACKUP>` | A backup's name, or latest | `latest` |

## Steps

### 1. A model

Model Admin > the model > Backups > Restore (over itself or as a new model).

### 2. A project

The project's About tab > Back up and restore.

### 3. A part

Backups > a backup > Restore > the databases, the files or the config (`<BACKUP>`: a backup's name, or latest).

Windows (PowerShell):

```
.\eax restore <BACKUP> --what db
```

Linux or macOS:

```
./eax.sh restore <BACKUP> --what db
```

### 4. Everything

Backups > a backup > Restore > everything: EA Explorer is read only meanwhile.

Windows (PowerShell):

```
.\eax restore <BACKUP> --what full
```

Linux or macOS:

```
./eax.sh restore <BACKUP> --what full
```

### 5. Check it

The integrity check runs by itself after every restore (guide: database checks).

Windows (PowerShell):

```
.\eax db integrity
```

Linux or macOS:

```
./eax.sh db integrity
```
