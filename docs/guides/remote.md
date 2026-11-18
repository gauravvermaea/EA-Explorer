# Any server over SSH

EA Explorer put on another machine from this one (no cloud-specific code, D746).

On screen: System Admin > Setup > Any server over SSH, where you fill in your values and get every command ready to copy. On the machine: `eax setup remote`. In Jenkins: the `setup` pipeline with `remote`.

## Steps

### 1. The plan

Which machine, how to reach it, laptop or server: the wizard asks.

Windows (PowerShell):

```
.\eax deploy --console --plan
```

Linux or macOS:

```
./eax.sh deploy --console --plan
```

### 2. Deploy

The code, the config file and the start, over SSH.

Windows (PowerShell):

```
.\eax deploy --console --yes
```

Linux or macOS:

```
./eax.sh deploy --console --yes
```

### 3. It appears in the site picker

Sites > the new site, green within five minutes.
