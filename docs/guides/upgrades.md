# Upgrades and rollbacks

A new release put in, and taken back out if needed.

On screen: System Admin > Setup > Upgrades and rollbacks, where you fill in your values and get every command ready to copy. On the machine: `eax setup upgrades`. In Jenkins: the `setup` pipeline with `upgrades`.

## Steps

### 1. What is new

The releases and their notes.

Windows (PowerShell):

```
.\eax update --list
```

Linux or macOS:

```
./eax.sh update --list
```

### 2. A backup first

Taken by the update itself too.

Windows (PowerShell):

```
.\eax backup
```

Linux or macOS:

```
./eax.sh backup
```

### 3. Update

To the newest release of your channel, or a named one.

Windows (PowerShell):

```
.\eax update
```

Linux or macOS:

```
./eax.sh update
```

### 4. Check it

The smoke test.

Windows (PowerShell):

```
.\eax test smoke
```

Linux or macOS:

```
./eax.sh test smoke
```

### 5. Roll back if needed

The release before, with its data as it was.

Windows (PowerShell):

```
.\eax rollback
```

Linux or macOS:

```
./eax.sh rollback
```
