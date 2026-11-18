# A laptop

EA Explorer on your own computer, to try it or to work alone.

On screen: System Admin > Setup > A laptop, where you fill in your values and get every command ready to copy. On the machine: `eax setup laptop`. In Jenkins: the `setup` pipeline with `laptop`.

## Steps

### 1. Docker runs

Docker Desktop installed and started; at least 16 GB of memory.

Windows (PowerShell):

```
.\eax check
```

Linux or macOS:

```
./eax.sh check
```

### 2. The config file

Answers laptop and password (or certificate).

Windows (PowerShell):

```
.\eax init laptop --password
```

Linux or macOS:

```
./eax.sh init laptop --password
```

### 3. Start

The core first (a few minutes), the rest in the background.

Windows (PowerShell):

```
.\eax up
```

Linux or macOS:

```
./eax.sh up
```

### 4. Trust the certificate

The browser stops warning about the laptop's own certificate.

Windows (PowerShell):

```
.\eax trust
```

Linux or macOS:

```
./eax.sh trust
```

### 5. Check it

The smoke test: every role signs in, every area answers.

Windows (PowerShell):

```
.\eax test smoke
```

Linux or macOS:

```
./eax.sh test smoke
```

### 6. Sign in

https://localhost: the logins are printed by eax logins.

Windows (PowerShell):

```
.\eax logins
```

Linux or macOS:

```
./eax.sh logins
```
