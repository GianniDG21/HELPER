-- Dati esempio settore VENDITA
INSERT INTO customers (id, name, email, phone) VALUES
    ('11111111-1111-1111-1111-111111111111', 'Maria Conti', 'maria.conti@email.it', '+39 333 1112233'),
    ('22222222-2222-2222-2222-222222222222', 'Referente Garino', 'ordini@garino-officina.it', '+39 011 4455667')
ON CONFLICT (id) DO NOTHING;

INSERT INTO tickets (
    id, customer_id, company_id, assigned_to, title, description, original_request, source_email,
    status, vehicle, part_code
) VALUES
    (1, '11111111-1111-1111-1111-111111111111',
     NULL, NULL,
     'Preventivo kit frizione Panda 1.2',
     'Cliente chiede preventivo completo frizione + manodopera stimata. Auto: Fiat Panda 2018.',
     NULL, 'maria.conti@email.it',
     'open', 'FH234ZZ', 'KTE-99821'),
    (2, '22222222-2222-2222-2222-222222222222',
     'eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee', 'f1010101-1010-1010-1010-101010101010',
     'Reclamo tempi consegna cerchi in lega',
     'Ordine 4 cerchi 17" in ritardo di 10 gg rispetto a DDT.',
     NULL, 'ordini@garino-officina.it',
     'in_progress', NULL, 'WHL-AL-17-X'),
    (3, '11111111-1111-1111-1111-111111111111',
     NULL, NULL,
     'Olio motore sbagliato in listino',
     'Consegnato 5W30 invece di 5W40. Cliente non ha montato.',
     NULL, 'maria.conti@email.it',
     'resolved', 'EL987BA', 'LUB-5W40-SYN')
ON CONFLICT (id) DO NOTHING;

SELECT setval(pg_get_serial_sequence('tickets', 'id'), (SELECT COALESCE(MAX(id), 1) FROM tickets));
