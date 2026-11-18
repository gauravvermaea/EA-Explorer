# A DR site

A second site kept up to date, ready to take over.

On screen: System Admin > Setup > A DR site, where you fill in your values and get every command ready to copy. On the machine: `eax setup dr-site`. In Jenkins: the `setup` pipeline with `dr-site`.

## Steps

### 1. The DR site

A server (the server guide) with the same release.

### 2. A pairing key on the DR site

System Admin > Site pairings > Make a key.

### 3. Pair from the primary

System Admin > Site pairings > Pair with a site: DR sync.

### 4. Accept on the DR site

It becomes read only, kept up to date every few minutes.

### 5. Rehearse

The restore drill, now and then.
