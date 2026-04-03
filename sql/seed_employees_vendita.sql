INSERT INTO employees (id, name, email) VALUES
    ('f1010101-1010-1010-1010-101010101010', 'Paola Ricambi', 'paola.r@vendita.officina.local'),
    ('f1020202-2020-2020-2020-202020202020', 'Marco Banco', 'marco.b@vendita.officina.local')
ON CONFLICT (id) DO NOTHING;
