CREATE EXTENSION IF NOT EXISTS "pgcrypto";

CREATE TABLE IF NOT EXISTS companies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    trade_name TEXT NOT NULL,
    legal_name TEXT NOT NULL,
    email_domain TEXT NOT NULL UNIQUE,
    suggested_helpdesk TEXT NOT NULL
        CHECK (suggested_helpdesk IN ('vendita', 'acquisto', 'manutenzione'))
);

CREATE TABLE IF NOT EXISTS employees (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    active BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS customers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    phone TEXT
);

-- POC: id numerico progressivo (più semplice da copiare in UI rispetto a UUID)
CREATE TABLE IF NOT EXISTS tickets (
    id BIGSERIAL PRIMARY KEY,
    customer_id UUID NOT NULL REFERENCES customers (id) ON DELETE CASCADE,
    company_id UUID REFERENCES companies (id) ON DELETE SET NULL,
    assigned_to UUID REFERENCES employees (id) ON DELETE SET NULL,
    title TEXT NOT NULL,
    description TEXT,
    original_request TEXT,
    source_email TEXT,
    status TEXT NOT NULL DEFAULT 'pending_acceptance'
        CHECK (status IN (
            'pending_acceptance',
            'open',
            'in_progress',
            'resolved'
        )),
    vehicle TEXT,
    part_code TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_tickets_customer ON tickets (customer_id);
CREATE INDEX IF NOT EXISTS idx_tickets_status ON tickets (status);
CREATE INDEX IF NOT EXISTS idx_tickets_assigned ON tickets (assigned_to);

-- Email simulate (POC): messaggi "in uscita" dal reparto verso il richiedente
CREATE TABLE IF NOT EXISTS simulated_emails (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ticket_id BIGINT NOT NULL REFERENCES tickets (id) ON DELETE CASCADE,
    to_email TEXT NOT NULL,
    subject TEXT NOT NULL,
    body TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_sim_emails_ticket ON simulated_emails (ticket_id);
CREATE INDEX IF NOT EXISTS idx_sim_emails_to_lower ON simulated_emails (lower(to_email));
