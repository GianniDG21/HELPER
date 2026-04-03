INSERT INTO employees (id, name, email) VALUES
    ('f3010101-1010-1010-1010-101010101012', 'Giulia Officina', 'giulia.o@manutenzione.officina.local'),
    ('f3020202-2020-2020-2020-202020202022', 'Davide Meccanico', 'davide.m@manutenzione.officina.local')
ON CONFLICT (id) DO NOTHING;
