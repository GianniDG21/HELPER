-- Schema aggiornato: vedi sql/schema.sql (ticket_id BIGINT). Per DB creati prima del passaggio a id numerico:
-- ricrea i volumi Docker o migra manualmente tickets/simulated_emails.
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
