# Inventario dati di seed — database POC

Riferimento statico dei **record iniziali** caricati dagli script in `sql/` dopo `docker compose up` (o `down -v` + `up`).  
I **ticket creati dall’intake** (`route_and_open_ticket`) hanno **UUID nuovi** e non compaiono qui: vanno letti direttamente da Postgres o dall’API.

Ogni reparto ha un **database Postgres separato** (stesso schema, dati di settore diversi per clienti/ticket/dipendenti; `companies` è allineata tra i tre).

| Reparto (helpdesk) | Porta host | URL `.env` tipico |
|--------------------|------------|-------------------|
| vendita            | **5433**   | `postgresql://team:team@localhost:5433/tickets` |
| acquisto           | **5434**   | `postgresql://team:team@localhost:5434/tickets` |
| manutenzione       | **5435**   | `postgresql://team:team@localhost:5435/tickets` |

Credenziali: utente `team`, password `team`, database `tickets`.

---

## Tabelle (schema)

| Tabella | Contenuto |
|---------|-----------|
| `companies` | Aziende / domini email e reparto suggerito |
| `employees` | Dipendenti del **solo** reparto di quel DB |
| `customers` | Clienti o contatti collegati ai ticket di esempio |
| `tickets` | Pratiche di esempio + campi opzionali (veicolo, codice ricambio, mail sorgente, …) |

Stati ammessi su `tickets.status`: `pending_acceptance`, `open`, `in_progress`, `resolved`.

---

## `companies` (identici nei tre DB)

| id (UUID) | trade_name | email_domain | suggested_helpdesk |
|-----------|------------|--------------|--------------------|
| `cccccccc-cccc-cccc-cccc-cccccccccccc` | Trasporti Nord | `trasportinord.it` | manutenzione |
| `dddddddd-dddd-dddd-dddd-dddddddddddd` | Disbrigo Ricambi | `disbrigo.it` | acquisto |
| `eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee` | Officina Garino | `garino-officina.it` | vendita |
| `b0b0b0b0-b0b0-b0b0-b0b0-b0b0b0b0b0b0` | Cliente generico | `email.it` | vendita |

Fonte: `sql/seed_companies.sql`.  
L’intake in app usa la stessa anagrafica in `app/intake/companies_registry.py` per `lookup_company_by_email`.

---

## `employees`

### Database **vendita** (porta 5433) — `sql/seed_employees_vendita.sql`

| id | name | email |
|----|------|--------|
| `f1010101-1010-1010-1010-101010101010` | Paola Ricambi | paola.r@vendita.officina.local |
| `f1020202-2020-2020-2020-202020202020` | Marco Banco | marco.b@vendita.officina.local |

### Database **acquisto** (porta 5434) — `sql/seed_employees_acquisto.sql`

| id | name | email |
|----|------|--------|
| `f2010101-1010-1010-1010-101010101011` | Sara Acquisti | sara.a@acquisto.officina.local |
| `f2020202-2020-2020-2020-202020202021` | Luca Fornitori | luca.f@acquisto.officina.local |

### Database **manutenzione** (porta 5435) — `sql/seed_employees_manutenzione.sql`

| id | name | email |
|----|------|--------|
| `f3010101-1010-1010-1010-101010101012` | Giulia Officina | giulia.o@manutenzione.officina.local |
| `f3020202-2020-2020-2020-202020202022` | Davide Meccanico | davide.m@manutenzione.officina.local |

---

## `customers` e `tickets` per settore

Chiavi: `customer_id`, `company_id`, `assigned_to` sono UUID FK verso `customers`, `companies`, `employees` (se valorizzati).

### **vendita** — `sql/seed_vendita.sql`

**Clienti**

| id | name | email | phone |
|----|------|-------|--------|
| `11111111-1111-1111-1111-111111111111` | Maria Conti | maria.conti@email.it | +39 333 1112233 |
| `22222222-2222-2222-2222-222222222222` | Referente Garino | ordini@garino-officina.it | +39 011 4455667 |

**Ticket di esempio**

| id | titolo | status | customer_id | company_id | assigned_to | source_email | vehicle | part_code |
|----|--------|--------|-------------|------------|-------------|--------------|---------|-----------|
| `aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa` | Preventivo kit frizione Panda 1.2 | open | `11111111-…` | — | — | maria.conti@email.it | FH234ZZ | KTE-99821 |
| `bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb` | Reclamo tempi consegna cerchi in lega | in_progress | `22222222-…` | `eeeeeeee-…` (Garino) | `f1010101-…` (Paola) | ordini@garino-officina.it | — | WHL-AL-17-X |
| `cccccccc-cccc-cccc-cccc-cccccccccccc` | Olio motore sbagliato in listino | resolved | `11111111-…` | — | — | maria.conti@email.it | EL987BA | LUB-5W40-SYN |

Nota: l’UUID `cccccccc-cccc-cccc-cccc-cccccccccccc` compare anche come **id azienda** «Trasporti Nord» nella tabella `companies`; in seed vendita è usato come **id ticket** — sono due entità diverse, solo collisione numerica di seed.

---

### **acquisto** — `sql/seed_acquisto.sql`

**Clienti**

| id | name | email | phone |
|----|------|-------|--------|
| `33333333-3333-3333-3333-333333333333` | Ufficio Acquisti Disbrigo | commerciale@disbrigo.it | +39 02 55667788 |
| `44444444-4444-4444-4444-444444444444` | Referente Batterie | logistica@batterieco.it | +39 051 3344556 |

**Ticket di esempio**

| id | titolo | status | customer_id | company_id | assigned_to | source_email | part_code |
|----|--------|--------|-------------|------------|-------------|--------------|-----------|
| `a1a1a1a1-a1a1-a1a1-a1a1-a1a1a1a1a1a1` | Fattura 4421: IVA aliquota errata | open | `33333333-…` | `dddddddd-…` (Disbrigo) | — | commerciale@disbrigo.it | BRK-PAD-R123 |
| `a2a2a2a2-a2a2-a2a2-a2a2-a2a2a2a2a2a2` | Mancata consegna pallet pastiglie Brembo | in_progress | `44444444-…` | — | `f2010101-…` (Sara) | logistica@batterieco.it | BRK-BRM-KIT |
| `a3a3a3a3-a3a3-a3a3-a3a3-a3a3a3a3a3a3` | Reso alternatore difettoso lotto L88 | resolved | `33333333-…` | `dddddddd-…` | — | commerciale@disbrigo.it | ALT-AG9921 |

---

### **manutenzione** — `sql/seed_manutenzione.sql`

**Clienti**

| id | name | email | phone |
|----|------|-------|--------|
| `55555555-5555-5555-5555-555555555555` | Luca Verdi | l.verdi@fastmail.it | +39 347 8899001 |
| `66666666-6666-6666-6666-666666666666` | Fleet Trasporti Nord | fleet@trasportinord.it | +39 045 9900112 |

**Ticket di esempio**

| id | titolo | status | customer_id | company_id | assigned_to | source_email | vehicle | part_code |
|----|--------|--------|-------------|------------|-------------|--------------|---------|-----------|
| `b1b1b1b1-b1b1-b1b1-b1b1-b1b1b1b1b1b1` | Climatizzatore non carica gas | open | `55555555-…` | — | — | l.verdi@fastmail.it | AB123CD | — |
| `b2b2b2b2-b2b2-b2b2-b2b2-b2b2b2b2b2b2` | Tagliando Scudo 2.0 ultra scaduto | in_progress | `66666666-…` | `cccccccc-…` (Trasporti Nord) | `f3010101-…` (Giulia) | fleet@trasportinord.it | FN445LM | FIL-KIT-2.0 |
| `b3b3b3b3-b3b3-b3b3-b3b3-b3b3b3b3b3b3` | Rumore assale posteriore in curva | open | `55555555-…` | — | — | l.verdi@fastmail.it | AB123CD | — |

---

## Query rapide (controllo manuale)

```sql
SELECT id, title, status, assigned_to FROM tickets ORDER BY created_at;
SELECT id, name, email FROM employees;
SELECT id, trade_name, email_domain FROM companies;
```

---

## Allineamento con la documentazione utente

Gli `employee_id` per la UI/API coincidono con la tabella dipendenti nel [README](../README.md). Per provare l’intake su dominio anagrafica usare email che terminano con i domini in `companies` (es. `...@trasportinord.it`, `...@disbrigo.it`).
