INSERT INTO customers (id, name, email, phone) VALUES
    ('33333333-3333-3333-3333-333333333333', 'Ufficio Acquisti Disbrigo', 'commerciale@disbrigo.it', '+39 02 55667788'),
    ('44444444-4444-4444-4444-444444444444', 'Referente Batterie', 'logistica@batterieco.it', '+39 051 3344556')
ON CONFLICT (id) DO NOTHING;

INSERT INTO tickets (
    id, customer_id, company_id, assigned_to, title, description, original_request, source_email,
    status, vehicle, part_code
) VALUES
    (1, '33333333-3333-3333-3333-333333333333',
     'dddddddd-dddd-dddd-dddd-dddddddddddd', NULL,
     'Fattura 4421: IVA aliquota errata',
     'Riga pastiglie con IVA 10% invece di 22%. Serve nota credito.',
     NULL, 'commerciale@disbrigo.it',
     'open', NULL, 'BRK-PAD-R123'),
    (2, '44444444-4444-4444-4444-444444444444',
     NULL, 'f2010101-1010-1010-1010-101010101011',
     'Mancata consegna pallet pastiglie Brembo',
     'DDT promesso 03/04, magazzino ancora vuoto. Ordine PO-7781.',
     NULL, 'logistica@batterieco.it',
     'in_progress', NULL, 'BRK-BRM-KIT'),
    (3, '33333333-3333-3333-3333-333333333333',
     'dddddddd-dddd-dddd-dddd-dddddddddddd', NULL,
     'Reso alternatore difettoso lotto L88',
     'Alternatore scorta: rumore cuscinetto dopo 200 km.',
     NULL, 'commerciale@disbrigo.it',
     'resolved', NULL, 'ALT-AG9921')
ON CONFLICT (id) DO NOTHING;

SELECT setval(pg_get_serial_sequence('tickets', 'id'), (SELECT COALESCE(MAX(id), 1) FROM tickets));
