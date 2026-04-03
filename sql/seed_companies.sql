-- Anagrafica condivisa (stesse righe nei tre DB)
INSERT INTO companies (id, trade_name, legal_name, email_domain, suggested_helpdesk) VALUES
    ('cccccccc-cccc-cccc-cccc-cccccccccccc', 'Trasporti Nord', 'Flotta Trasporti Nord Srl', 'trasportinord.it', 'manutenzione'),
    ('dddddddd-dddd-dddd-dddd-dddddddddddd', 'Disbrigo Ricambi', 'Disbrigo Ricambi Srl', 'disbrigo.it', 'acquisto'),
    ('eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee', 'Officina Garino', 'Garino SNC', 'garino-officina.it', 'vendita'),
    ('b0b0b0b0-b0b0-b0b0-b0b0-b0b0b0b0b0b0', 'Cliente generico', 'Contatti esterni', 'email.it', 'vendita')
ON CONFLICT (id) DO NOTHING;
