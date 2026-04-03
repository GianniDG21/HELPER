INSERT INTO customers (id, name, email, phone) VALUES
    ('55555555-5555-5555-5555-555555555555', 'Luca Verdi', 'l.verdi@fastmail.it', '+39 347 8899001'),
    ('66666666-6666-6666-6666-666666666666', 'Fleet Trasporti Nord', 'fleet@trasportinord.it', '+39 045 9900112')
ON CONFLICT (id) DO NOTHING;

INSERT INTO tickets (
    id, customer_id, company_id, assigned_to, title, description, original_request, source_email,
    status, vehicle, part_code
) VALUES
    (1, '55555555-5555-5555-5555-555555555555',
     NULL, NULL,
     'Climatizzatore non carica gas',
     'Golf VII 2016. Pratica vuota dopo ricarica esterna.',
     NULL, 'l.verdi@fastmail.it',
     'open', 'AB123CD', NULL),
    (2, '66666666-6666-6666-6666-666666666666',
     'cccccccc-cccc-cccc-cccc-cccccccccccc', 'f3010101-1010-1010-1010-101010101012',
     'Tagliando Scudo 2.0 ultra scaduto',
     'Furgone FN445LM: alert manutenzione +2000 km.',
     NULL, 'fleet@trasportinord.it',
     'in_progress', 'FN445LM', 'FIL-KIT-2.0'),
    (3, '55555555-5555-5555-5555-555555555555',
     NULL, NULL,
     'Rumore assale posteriore in curva',
     'Sintomo dopo sostituzione molle.',
     NULL, 'l.verdi@fastmail.it',
     'open', 'AB123CD', NULL)
ON CONFLICT (id) DO NOTHING;

SELECT setval(pg_get_serial_sequence('tickets', 'id'), (SELECT COALESCE(MAX(id), 1) FROM tickets));
