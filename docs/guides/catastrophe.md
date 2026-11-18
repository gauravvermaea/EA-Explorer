# A catastrophic failure

The machine or its data is lost: what to do first, who to tell, what to check.

On screen: System Admin > Setup > A catastrophic failure, where you fill in your values and get every command ready to copy. On the machine: `eax setup catastrophe`. In Jenkins: the `setup` pipeline with `catastrophe`.

## Steps

### 1. Stop and look

What is lost: the machine, the disk, the data, or only EA Explorer.

Windows (PowerShell):

```
.\eax status
```

Linux or macOS:

```
./eax.sh status
```

### 2. Tell people

The banner (System Admin > Banner) and the people who rely on it.

### 3. The newest good backup

On this machine, the share, or a DR pack kept elsewhere.

Windows (PowerShell):

```
.\eax backups
```

Linux or macOS:

```
./eax.sh backups
```

### 4. A DR site?

If there is one, switch to it (guide: switch to DR).

### 5. Otherwise rebuild

On a new machine from the backup (guide: rebuild).
