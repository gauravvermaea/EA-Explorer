# Sync and DR pairings

Content sync or DR sync between two sites.

On screen: System Admin > Setup > Sync and DR pairings, where you fill in your values and get every command ready to copy. On the machine: `eax setup pairings`. In Jenkins: the `setup` pipeline with `pairings`.

## Steps

### 1. A key on the receiving site

System Admin > Site pairings > Make a key: shown once.

### 2. Pair from the sending site

Its address, the key, content or DR; by hand or by itself.

### 3. Accept

On the receiving site: commit by hand (look first) or by itself.

### 4. Sync now

On the sending site; the batches show what arrived and what was committed.
