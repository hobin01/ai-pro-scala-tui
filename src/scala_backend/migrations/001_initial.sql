CREATE TABLE IF NOT EXISTS scala_settings (
    setting_key TEXT PRIMARY KEY,
    setting_value JSONB NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS scala_runs (
    run_id UUID PRIMARY KEY,
    status TEXT NOT NULL CHECK (status IN ('running', 'completed', 'failed')),
    selected_sources JSONB NOT NULL,
    doc_count INT,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS scala_agent_usage (
    id BIGSERIAL PRIMARY KEY,
    run_id UUID NOT NULL REFERENCES scala_runs(run_id),
    agent TEXT NOT NULL,
    model TEXT,
    prompt_tokens INT NOT NULL DEFAULT 0,
    completion_tokens INT NOT NULL DEFAULT 0,
    total_tokens INT NOT NULL DEFAULT 0,
    cost_usd NUMERIC NOT NULL DEFAULT 0,
    last_activity TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (run_id, agent)
);

CREATE TABLE IF NOT EXISTS scala_data_lineage_metadata (
    id BIGSERIAL PRIMARY KEY,
    run_id UUID NOT NULL REFERENCES scala_runs(run_id),
    source_solution TEXT NOT NULL,
    source_index TEXT NOT NULL,
    source_doc_id TEXT NOT NULL,
    opensearch_index TEXT NOT NULL,
    opensearch_id TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_scala_lineage_opensearch_id
    ON scala_data_lineage_metadata (opensearch_id);
