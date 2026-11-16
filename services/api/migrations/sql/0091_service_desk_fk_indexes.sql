-- =====================================================================================
-- 0091_service_desk_fk_indexes: the service desk's two foreign keys without an index (R5.47; the full self-test of
-- 16 Nov 2026: "foreign keys have an index (speed): core.service_tickets(type_key); core.service_ticket_files(ticket_id)").
-- A ticket's files are read with the ticket, and a request type's tickets when the type changes or is removed: without
-- an index each reads the whole table. Indexes only; no logic (D248).
-- =====================================================================================

CREATE INDEX IF NOT EXISTS service_tickets_type_idx ON core.service_tickets (type_key);
CREATE INDEX IF NOT EXISTS service_ticket_files_ticket_idx ON core.service_ticket_files (ticket_id);
