-- Database centralizzato «pratiche»: registro aperture con richiedente e timestamp.
-- Ogni riga è collegata a un ticket nel DB di settore (sector_ticket_id).

CREATE TABLE IF NOT EXISTS pratiche (
    id BIGSERIAL PRIMARY KEY,
    department TEXT NOT NULL
        CHECK (department IN ('vendita', 'acquisto', 'manutenzione')),
    sector_ticket_id BIGINT NOT NULL,
    requested_by_name TEXT NOT NULL,
    requested_by_email TEXT NOT NULL,
    requested_by_phone TEXT,
    company_id UUID,
    title TEXT NOT NULL,
    full_summary TEXT,
    vehicle TEXT,
    part_code TEXT,
    status TEXT NOT NULL DEFAULT 'pending_acceptance'
        CHECK (status IN (
            'pending_acceptance',
            'open',
            'in_progress',
            'resolved'
        )),
    assigned_to UUID,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    accepted_at TIMESTAMPTZ,
    CONSTRAINT uq_pratiche_dept_sector UNIQUE (department, sector_ticket_id)
);

CREATE INDEX IF NOT EXISTS idx_pratiche_dept_status ON pratiche (department, status);
CREATE INDEX IF NOT EXISTS idx_pratiche_created ON pratiche (created_at DESC);
