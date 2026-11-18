# Database checks

Integrity and recent records, weekly and after restores (R6.6.1).

On screen: System Admin > Setup > Database checks, where you fill in your values and get every command ready to copy. On the machine: `eax setup db-checks`. In Jenkins: the `setup` pipeline with `db-checks`.

## Steps

### 1. Check now

Every database: indexes, tables, constraints, sequences, the newest records.

Windows (PowerShell):

```
.\eax db integrity
```

Linux or macOS:

```
./eax.sh db integrity
```

### 2. Safe fixes

Made by themselves after a backup; the admins are told.

### 3. Orphan rows

Database maintenance > Integrity > Preview the repair (Super Admins).
