INSERT INTO employees (id, name, email) VALUES
    ('f2010101-1010-1010-1010-101010101011', 'Sara Acquisti', 'sara.a@acquisto.officina.local'),
    ('f2020202-2020-2020-2020-202020202021', 'Luca Fornitori', 'luca.f@acquisto.officina.local')
ON CONFLICT (id) DO NOTHING;
