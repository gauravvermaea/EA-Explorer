-- =====================================================================================
-- 0104_r6_5_site_pairings: site pairings and sync batches (Release 6.5; owner, 17 Nov 2026, 19:30 to 19:40;
--   D749). Site 1 is given Site 2's address and a pairing key made on Site 2; Site 2 accepts. One way only: Site 1 sends,
--   Site 2 takes what is sent over its own (changes there are overridden). Content sync carries content only; DR sync
--   carries content and the users and their roles, is committed by itself and keeps Site 2 read only.
--   Each batch has a sequence number per pairing and a reply; the queue is these rows (the files beside them on disk,
--   under the backups folder. (Promotion is not here: packages are downloaded and uploaded where they always were, and a
--   git repository is one more place for them.)
--   Tables and indexes only; no logic (D248).
-- =====================================================================================

CREATE TABLE IF NOT EXISTS core.site_pairings (
    id               bigint      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    guid             uuid        NOT NULL DEFAULT gen_random_uuid() UNIQUE,
    side             text        NOT NULL CHECK (side IN ('sender', 'receiver')),
    name             text        NOT NULL CHECK (btrim(name) <> '' AND length(name) <= 120),
    peer_url         text        NOT NULL DEFAULT '' CHECK (length(peer_url) <= 500),
    peer_name        text        NOT NULL DEFAULT '',
    peer_guid        uuid,                                   -- the same pairing's id on the other site
    peer_pin         text        NOT NULL DEFAULT '',        -- the other site's certificate (SHA-256), when trusted by hand
    kind             text        NOT NULL DEFAULT 'content' CHECK (kind IN ('content', 'dr')),
    status           text        NOT NULL DEFAULT 'waiting'
                                 CHECK (status IN ('key', 'waiting', 'accepted', 'refused', 'stopped')),
    commit_mode      text        NOT NULL DEFAULT 'manual' CHECK (commit_mode IN ('manual', 'auto')),
    send_mode        text        NOT NULL DEFAULT 'manual' CHECK (send_mode IN ('manual', 'auto')),
    every_minutes    integer     NOT NULL DEFAULT 60 CHECK (every_minutes BETWEEN 5 AND 10080),
    scope            jsonb       NOT NULL DEFAULT '{"all": true}'::jsonb,
    key_enc          bytea,                                  -- the sender's copy of the key, encrypted (EAX_REMOTE_SECRET_KEY)
    key_hash         text,                                   -- the receiver's: only its hash
    next_seq         bigint      NOT NULL DEFAULT 1,         -- the sender: the next batch's number
    last_seq         bigint      NOT NULL DEFAULT 0,         -- the receiver: the last batch taken in order
    last_sent_at     timestamptz,
    last_received_at timestamptz,
    last_auto_at     timestamptz,
    last_error       text        NOT NULL DEFAULT '',
    note             text        NOT NULL DEFAULT '',
    created_by       text        NOT NULL DEFAULT 'system',
    created_at       timestamptz NOT NULL DEFAULT now(),
    modified_at      timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS site_pairings_name ON core.site_pairings (side, lower(name));
COMMENT ON TABLE core.site_pairings IS 'R6.5: pairings with other EA Explorer sites (one way: the sender to the receiver)';

CREATE TABLE IF NOT EXISTS core.sync_batches (
    id            bigint      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    guid          uuid        NOT NULL DEFAULT gen_random_uuid() UNIQUE,
    pairing_id    bigint      NOT NULL REFERENCES core.site_pairings (id) ON DELETE CASCADE,
    direction     text        NOT NULL CHECK (direction IN ('out', 'in')),
    seq           bigint      NOT NULL DEFAULT 0,
    status        text        NOT NULL CHECK (status IN ('queued', 'sending', 'sent', 'failed',
                                                         'received', 'waiting', 'committing', 'committed', 'discarded')),
    items         jsonb       NOT NULL DEFAULT '[]'::jsonb,  -- what it holds: kind, id, name, hash
    file          text        NOT NULL DEFAULT '',           -- its zip, under <backups>/sync
    sha256        text        NOT NULL DEFAULT '',
    size          bigint      NOT NULL DEFAULT 0,
    attempts      integer     NOT NULL DEFAULT 0,
    reply         jsonb,
    error         text        NOT NULL DEFAULT '',
    notes         jsonb       NOT NULL DEFAULT '[]'::jsonb,
    created_by    text        NOT NULL DEFAULT 'system',
    created_at    timestamptz NOT NULL DEFAULT now(),
    sent_at       timestamptz,
    committed_at  timestamptz,
    committed_by  text
);
CREATE UNIQUE INDEX IF NOT EXISTS sync_batches_seq ON core.sync_batches (pairing_id, direction, seq);
CREATE INDEX IF NOT EXISTS sync_batches_open ON core.sync_batches (status) WHERE status IN ('queued', 'sending', 'received', 'waiting');
COMMENT ON TABLE core.sync_batches IS 'R6.5: the sync queue (out on the sender, in on the receiver)';

CREATE TABLE IF NOT EXISTS core.sync_sent (
    pairing_id  bigint      NOT NULL REFERENCES core.site_pairings (id) ON DELETE CASCADE,
    kind        text        NOT NULL,
    item        text        NOT NULL,
    hash        text        NOT NULL,
    sent_at     timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (pairing_id, kind, item)
);
COMMENT ON TABLE core.sync_sent IS 'R6.5: what an automatic sync last sent of each item, so only what changed goes again';

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'eax_app') THEN
        GRANT SELECT, INSERT, UPDATE, DELETE ON core.site_pairings, core.sync_batches, core.sync_sent TO eax_app;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'eax_migrator') THEN
        GRANT SELECT, INSERT, UPDATE, DELETE ON core.site_pairings, core.sync_batches, core.sync_sent TO eax_migrator;
    END IF;
END;
$$;
