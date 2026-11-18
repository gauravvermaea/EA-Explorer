# A new machine

A machine made ready for EA Explorer: Docker, disk, folders, network.

On screen: System Admin > Setup > A new machine, where you fill in your values and get every command ready to copy. On the machine: `eax setup new-machine`. In Jenkins: the `setup` pipeline with `new-machine`.

## Steps

### 1. Docker

Docker installed; at least 16 GB of memory and 100 GB of disk for a server.

Windows (PowerShell):

```
.\eax check
```

Linux or macOS:

```
./eax.sh check
```

### 2. Folders

Where data, backups and logs live (EAX_DATA_DIR, EAX_BACKUP_DIR, EAX_LOGS_DIR).

Windows (PowerShell):

```
.\eax folders
```

Linux or macOS:

```
./eax.sh folders
```

### 3. Network

Port 443 open to people; nothing else needs to be.

### 4. Then

The laptop or server guide.
