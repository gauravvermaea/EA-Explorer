# Switching to DR and back

The DR site takes over; later the primary comes back.

On screen: System Admin > Setup > Switching to DR and back, where you fill in your values and get every command ready to copy. On the machine: `eax setup switch-to-dr`. In Jenkins: the `setup` pipeline with `switch-to-dr`.

## Steps

### 1. Take over

On the DR site: System Admin > Site pairings > the DR pairing > Stop and take over.

### 2. Point people at it

The address people open (DNS) moved to the DR site.

### 3. Check it

The integrity check runs by itself when it takes over.

Windows (PowerShell):

```
.\eax db integrity
```

Linux or macOS:

```
./eax.sh db integrity
```

### 4. Fail back

Pair the other way (the DR site sends), then switch back the same way.
