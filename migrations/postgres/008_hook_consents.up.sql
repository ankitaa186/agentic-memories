-- Hook consent storage
-- Stores connector authorization payloads and metadata per user/hook.

CREATE TABLE IF NOT EXISTS hook_consents (
    id BIGSERIAL PRIMARY KEY,
    hook_name TEXT NOT NULL,
    user_id TEXT NOT NULL,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS hook_consents_hook_user_idx
    ON hook_consents (hook_name, user_id);

CREATE INDEX IF NOT EXISTS hook_consents_updated_idx
    ON hook_consents (updated_at DESC);

CREATE OR REPLACE FUNCTION set_hook_consents_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_hook_consents_updated ON hook_consents;
CREATE TRIGGER trg_hook_consents_updated
    BEFORE UPDATE ON hook_consents
    FOR EACH ROW
    EXECUTE FUNCTION set_hook_consents_updated_at();
