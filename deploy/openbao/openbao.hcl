# The key vault's configuration (R4.19, D684): OpenBao keeps EA Explorer's passwords and keys (eaxcli/vault.py).
# Its data in a file store on its own volume (eax-vault, in every infrastructure backup, sealed); reached on the
# backend network as http://openbao:8200 and from this computer only on 127.0.0.1 (EAX_VAULT_PORT), never from outside.
# One unseal key and the root token are kept in work/vault/keys.json, readable by the owner only; the vault unseals
# by itself at eax up, on a laptop and on a server alike (owner, 14 Nov 2026).

storage "file" {
  path = "/openbao/file/data"
}

listener "tcp" {
  address     = "0.0.0.0:8200"
  tls_disable = true      # inside the backend network and on 127.0.0.1 only; no port reaches another machine
}

# the audit log: every request, with the values hashed, into the vault's own volume (/openbao/file/audit), switched
# on through the API by eax up (eaxcli/vault.py audit_on); eax secrets says whether it is on

disable_mlock = true      # a container without IPC_LOCK; its memory is not swapped to disk in Docker Desktop's VM
ui            = false
log_level     = "warn"
