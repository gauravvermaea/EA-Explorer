# Building an environment from a backup

A new machine made from a backup or a DR pack, nothing lost.

On screen: System Admin > Setup > Building an environment from a backup, where you fill in your values and get every command ready to copy. On the machine: `eax setup rebuild` with `--set KEY=VALUE` for each value. In Jenkins: the `setup` pipeline with `rebuild`.

## Your values

| Value | What it is | For example |
|---|---|---|
| `<PACK>` | The folder for the DR pack | `D:/dr-packs` |
| `<INSTALL>` | The folder EA Explorer is put in on the new machine | `C:/EA-Explorer` |

## Steps

### 1. The pack

A DR pack (eax dr-pack) or a backup folder, with its env file.

### 2. Docker on the new machine

The new machine guide.

Windows (PowerShell):

```
.\eax check
```

Linux or macOS:

```
./eax.sh check
```

### 3. Build and restore

On the new machine, from the pack in `<PACK>` into `<INSTALL>`: the code, the config, the restore, compared.

Windows (PowerShell):

```
.\dr\eax-dr.ps1 -Pack <PACK> -Install <INSTALL>
```

Linux or macOS:

```
./dr/eax-dr.sh --pack <PACK> --install <INSTALL>
```

### 4. Check it

The integrity check and the key items.

Windows (PowerShell):

```
.\eax db integrity
```

Linux or macOS:

```
./eax.sh db integrity
```
