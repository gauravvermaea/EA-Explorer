# Jenkins

A pipeline per eax command and DR tool, a click away (R6.6-J1).

On screen: System Admin > Setup > Jenkins, where you fill in your values and get every command ready to copy. On the machine: `eax setup jenkins`. In Jenkins: the `setup` pipeline with `jenkins`.

## Steps

### 1. Start it

Its own stack, the agent on this machine, the pipelines written.

Windows (PowerShell):

```
.\eax jenkins up
```

Linux or macOS:

```
./eax.sh jenkins up
```

### 2. Sign in

With EA Explorer (Super or IT Admin), or Jenkins' own account when Keycloak is down.

Windows (PowerShell):

```
.\eax jenkins status
```

Linux or macOS:

```
./eax.sh jenkins status
```

### 3. Run a pipeline

eax > a command > Build with parameters; those that change everything ask for the installation's name.
