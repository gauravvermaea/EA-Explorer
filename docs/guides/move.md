# Moving to a new machine

A laptop to a server, or one server to another, nothing lost.

On screen: System Admin > Setup > Moving to a new machine, where you fill in your values and get every command ready to copy. On the machine: `eax setup move` with `--set KEY=VALUE` for each value. In Jenkins: the `setup` pipeline with `move`.

## Your values

| Value | What it is | For example |
|---|---|---|
| `<PACK>` | The folder for the DR pack | `D:/dr-packs` |
| `<INSTALL>` | The folder EA Explorer is put in on the new machine | `C:/EA-Explorer` |

## Steps

### 1. A DR pack on the old machine

Everything in one folder (`<PACK>`), checked; copy it to the new machine.

Windows (PowerShell):

```
.\eax dr-pack <PACK>
```

Linux or macOS:

```
./eax.sh dr-pack <PACK>
```

### 2. The new machine

The new machine guide.

### 3. Build from the pack

On the new machine, from `<PACK>` into `<INSTALL>`.

Windows (PowerShell):

```
.\dr\eax-dr.ps1 -Pack <PACK> -Install <INSTALL>
```

Linux or macOS:

```
./dr/eax-dr.sh --pack <PACK> --install <INSTALL>
```

### 4. Point people at it

The address moved; the old machine stopped.
