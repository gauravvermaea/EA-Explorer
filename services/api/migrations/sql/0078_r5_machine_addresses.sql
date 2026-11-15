-- =====================================================================================
-- 0078_r5_machine_addresses: R5.2 (D686): a machine credential may be limited to its own addresses (an address or a
--   range each; empty: from anywhere), checked at every call by the API. A column only (D248: no logic here).
-- =====================================================================================

ALTER TABLE core.machine_credentials ADD COLUMN IF NOT EXISTS allowed_addresses text[] NOT NULL DEFAULT '{}';
COMMENT ON COLUMN core.machine_credentials.allowed_addresses IS
    'R5.2: the addresses or ranges (CIDR) this credential may be used from; empty: from anywhere';
