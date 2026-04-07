# POC — Helpdesk smistamento richieste + assistenza dipendente

Prototipo (**POC**) che simula l’arrivo di una **richiesta unificata** (mail/chat), lo **smistamento verso il reparto corretto** (tre database Postgres indipendenti) e la **chat operativa** per il dipendente dopo la **presa in carico** della pratica.

**Manuale operativo (utenti interfaccia, con esempi):** [docs/MANUALE_OPERATIVO.md](docs/MANUALE_OPERATIVO.md)  
**Guida pratica step-by-step:** [docs/GUIDA_UTILIZZO_POC.md](docs/GUIDA_UTILIZZO_POC.md)  
**Record di seed nei DB (traccia UUID):** [docs/DATI_DATABASE_POC.md](docs/DATI_DATABASE_POC.md)  
**Sicurezza (chiave API opzionale, hardening):** [docs/SECURITY.md](docs/SECURITY.md)

---

## Obiettivo e flusso funzionale

1. **Intake** — `POST /intake/chat`: messaggio del “cliente”. L’agente (LangGraph + LLM locale Ollama o Groq cloud) usa tool per **anagrafica** (`lookup_company_by_email`), **elenco reparti** (`list_helpdesks`) e, raccolti **contatti** e **dati operativi minimi** (es. anno + km per veicolo, quantità per ricambi), prova ad aprire il ticket con `route_and_open_ticket`. È presente una **guardia server-side**: se i dati operativi non sono completi il ticket **non viene aperto** anche se il modello chiama il tool. Per le targhe veicolo è richiesto formato italiano **AA123BB** (due lettere, tre cifre, due lettere). Stato iniziale del ticket: **`pending_acceptance`** (e riga nel registry **pratiche**).
2. **Coda / elenco** — `GET /departments/{reparto}/tickets/pending`: solo pratiche **in attesa di accettazione** per quel reparto. **`GET /departments/{reparto}/pratiche`**: **tutte** le pratiche del reparto (ogni stato) con **nome operatore assegnato** (per UI operatore). **`GET /pratiche`**: stesso formato su **tutti** i reparti (vista unificata). `GET /pratiche/pending`: coda globale su tutti i reparti.
3. **Presa in carico** — `POST /departments/{reparto}/tickets/{id}/accept` con `employee_id`: ticket in **`in_progress`** e assegnato al dipendente (allineato su DB reparto e registry pratiche).
4. **Messaggio al richiedente** — `POST /departments/{reparto}/pratiche/{pratica_id}/mail-richiedente` (body: `employee_id`, `subject`, `body`): registra email simulata verso il richiedente (**solo** se pratica `in_progress` e assegnata a quell’`employee_id`). Alternativa: tool in **`POST /assist/chat`**.
5. **Chiusura** — `POST /departments/{reparto}/pratiche/{pratica_id}/resolve` con `employee_id`: pratica e ticket di reparto in **`resolved`** (**solo** assegnatario in `in_progress`).
6. **Assistenza** — `POST /assist/chat`: chat multi-turno **solo** se il ticket è `in_progress` e **assegnato** al dipendente indicato nel body.

**Interfaccia web**

| URL | Uso |
|-----|-----|
| **http://127.0.0.1:8000/ui/** | Vista **tecnica** (traccia, pannello esito API, suggerimenti con riferimenti agli endpoint). |
| **http://127.0.0.1:8000/ui/clean.html** o **http://127.0.0.1:8000/ui/index.html?clean=1** | Vista **pulita** (testi per l’utente finale, senza dettagli API nella UI). |

Tab *Richiesta* (intake) e *Dipendente* (elenco pratiche per reparto o unificato, presa in carico, chiusura pratica, messaggio al richiedente, chat assistente). In UI il reparto `manutenzione` è mostrato come **officina**.

Selettore modello in header UI:
- **Locale (Ollama)** / **Remoto (Groq)**, persistito nel browser.
- Ogni chiamata API invia `X-LLM-Provider`.
- Se un provider non è disponibile, viene disabilitato in UI.

### Diagramma logico (alto livello)

```mermaid
flowchart LR
  subgraph intake[Intake]
    M[Messaggio cliente]
    A[Agente + tool]
    M --> A
    A --> DB1[(DB vendita)]
    A --> DB2[(DB acquisto)]
    A --> DB3[(DB manutenzione)]
  end
  subgraph desk[Operatore]
    Q[Coda pending]
    ACC[Prendi in carico]
    CHAT[Assist chat]
    Q --> ACC --> CHAT
  end
  DB1 & DB2 & DB3 --> Q
```

---

## Stack tecnico

| Componente | Uso |
|------------|-----|
| **FastAPI** | API HTTP, montaggio static `/ui` |
| **LangGraph** | Grafi intake e assist (fasi missione → ricognizione → … ) |
| **LangChain** | LLM: **Ollama** locale (`OLLAMA_MODEL`, default in `.env.example`) oppure **Groq** (`GROQ_MODEL`) |
| **asyncpg** | Accesso ai tre database |
| **MemorySaver** | Checkpointer in RAM per thread conversazione |

Struttura cartelle rilevante:

- `app/main.py` — endpoint e wiring grafi
- `app/agent/` — grafi, prompt, traccia UI-friendly
- `app/tools/` — tool intake e ticket per reparto
- `sql/` — schema e seed per reparto
- `static/` — UI statica (`index.html` vista tecnica, `clean.html` → vista pulita)

---

## Prerequisiti

- **Python 3.11+**
- **Docker Desktop** (o Docker Engine) per i Postgres dei reparti e il DB **pratiche** (`docker-compose.yml`)
- **Ollama** ([ollama.com](https://ollama.com)): `ollama pull qwen2.5:7b` (o altro modello testuale; vedi `OLLAMA_MODEL` in `.env.example`). In alternativa, account **Groq** e [API key](https://console.groq.com) con `LLM_PROVIDER=groq`.

---

## Configurazione

1. Copia l’esempio delle variabili:

   ```powershell
   Copy-Item .env.example .env
   ```

2. Con **Ollama** (default): `LLM_PROVIDER=ollama`, avvia Ollama e scarica il modello indicato da `OLLAMA_MODEL`. Con **Groq**: `LLM_PROVIDER=groq` e **`GROQ_API_KEY`**. Le URL DB di default puntano a `localhost:6433`–`6436` (allineate a `docker-compose.yml`).

---

## Database (Postgres in Docker)

Avvio manuale dei container:

```powershell
docker compose up -d
```

Reset completo (dati persi):

```powershell
docker compose down -v
docker compose up -d
```

**DB già esistenti** (volumi non ricreati): aggiungere la tabella email simulate eseguendo `sql/patch_simulated_emails.sql` su ciascuna istanza (porte 5433, 5434, 5435), oppure `down -v` e ricreazione da `schema.sql` aggiornato.

| Servizio             | Porta host | Utente / password / DB |
|----------------------|------------|-------------------------|
| `postgres_vendita`   | **6433**   | `team` / `team` / `tickets` |
| `postgres_acquisto`  | **6434**   | idem |
| `postgres_manutenzione` | **6435** | idem |
| `pratiche`           | **6436**   | `team` / `team` / `pratiche` (registry pratiche) |

---

## Avvio applicazione

### Avvio rapido (Docker + API)

Dopo la **prima volta** (venv + `pip install -r requirements.txt` e `.env` da `.env.example`), puoi usare lo script che avvia **tutti** i servizi Compose e poi **uvicorn**:

**Windows (PowerShell), dalla root del repo:**

```powershell
.\scripts\start.ps1
```

Se l’esecuzione degli script è bloccata: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` oppure `powershell -ExecutionPolicy Bypass -File .\scripts\start.ps1`.

**Linux / macOS / Git Bash:**

```bash
chmod +x scripts/start.sh   # una tantum
./scripts/start.sh
```

Variabile opzionale **`HELPER_PORT`** (default `8000`): es. `$env:HELPER_PORT = "8001"` in PowerShell, oppure `HELPER_PORT=8001 ./scripts/start.sh`.

Lo script **non** avvia Ollama: con provider Ollama avvialo separatamente.

### Avvio manuale

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
docker compose up -d
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

- **Health:** `GET http://127.0.0.1:8000/health`
- **OpenAPI / Swagger:** http://127.0.0.1:8000/docs
- **UI tecnica:** http://127.0.0.1:8000/ui/
- **UI pulita:** http://127.0.0.1:8000/ui/clean.html

**UI o browser non si connette**

- Controlla che **uvicorn** sia avviato dalla **root del repo** e che la porta sia quella giusta (default **8000**, oppure `HELPER_PORT`).
- Apri **`http://127.0.0.1:8000/ui/`** (o la porta usata). **`http://127.0.0.1:8000/health`**: se vedi `"database": false` o `"status": "degraded"`, Postgres non è raggiungibile: esegui **`docker compose up -d`** e verifica **`.env`**: le URL devono essere `postgresql://team:team@localhost:6433` … `6436` come in **`.env.example`** (se manca utente/password nel DSN, alcuni client usano l’utente di sistema Windows e la connessione fallisce).
- Con il DB fermo, la **pagina statica** `/ui` si carica comunque; le chiamate API (intake, elenco pratiche, ecc.) rispondono **503** finché i container non sono pronti.

### Test automatici

**Non richiedono Docker** (default): `tests/conftest.py` punta i Postgres a una porta inesistente, l’app parte in modalità `degraded` e i test verificano `/health`, `/openapi.json`, il blocco **503** su `/intake/chat` e funzioni pure (UUID, parsing id, forma API pratiche, validatori Pydantic).

**Valutazione intake (golden, senza LLM):** il file `eval/intake_golden_scenarios.json` elenca scenari sintetici (ToolMessage `route_and_open_ticket`); `tests/test_intake_golden_routing.py` verifica l’estrazione di `ticket_id` e reparto e il caso «doppia apertura nello stesso turno» (prevale **l’ultimo** tool valido). Solo golden routing:

```powershell
python -m pytest tests/test_intake_golden_routing.py -v
```

**Fallback intake lato server** (`INTAKE_FALLBACK_OPEN`): se il modello non invoca il tool ma il gate euristica è soddisfatto, l’API può aprire comunque la pratica. In quel caso nei log compare una riga **`WARNING`** `intake_fallback_open_applied` (con dominio email e anteprima titolo); i motivi per cui il fallback *non* scatta sono tracciati a livello **`DEBUG`** (`intake_fallback_open skipped: …`).

**Guardia apertura tool** (`route_and_open_ticket`): anche con tool-call esplicita, il backend valida i requisiti operativi minimi (veicolo/ricambi) prima dell’inserimento DB. Se il gate non è soddisfatto, risponde con `opened=false` e messaggio cliente-ready; non viene creata alcuna pratica.

```powershell
pip install -r requirements-dev.txt
python -m pytest
```

Per eseguire in futuro test **con** database reale (marker `integration`, da ampliare): imposta `HELPER_TEST_USE_REAL_DB=1` e avvia `docker compose`; le URL in `.env` devono essere raggiungibili.

---

## API — estratto

Tutti i dettagli (schemi, try-it-out) sono in **`/docs`**.

| Metodo | Path | Descrizione |
|--------|------|-------------|
| `POST` | `/intake/chat` | Messaggio cliente; opzionale `thread_id`. Risposta: `reply`, `trace`, e se il tool ha aperto la pratica **`routed_department`** + **`ticket_id`** |
| `GET`  | `/intake/thread` | Trascript conversazione intake (solo messaggi user/assistant “puliti”) |
| `GET`  | `/intake/simulated-mails?ticket_id=` | Email simulate inviate dal reparto verso il richiedente (POC) |
| `GET`  | `/departments/{dept}/employees` | Dipendenti attivi del reparto (`id`, `name`) — es. menu UI |
| `GET`  | `/departments/{dept}/tickets/pending` | Coda `pending_acceptance` per `vendita` \| `acquisto` \| `manutenzione` |
| `GET`  | `/departments/{dept}/pratiche` | Tutte le pratiche del reparto (ogni stato) + `assigned_to_name` |
| `GET`  | `/pratiche` | Tutte le pratiche di **tutti** i reparti (stesso schema + `assigned_to_name`) |
| `GET`  | `/pratiche/pending` | Coda `pending_acceptance` su **tutti** i reparti (registry centrale) |
| `POST` | `/departments/{dept}/tickets/{ticket_id}/accept` | Body: `{ "employee_id": "..." }` — `ticket_id` = id registry pratiche |
| `POST` | `/departments/{dept}/pratiche/{pratica_id}/mail-richiedente` | Body: `employee_id`, `subject`, `body` — email simulata al richiedente (stesso vincolo assegnazione di assist) |
| `POST` | `/departments/{dept}/pratiche/{pratica_id}/resolve` | Body: `{ "employee_id": "..." }` — chiusura `resolved` (solo assegnatario, `in_progress`) |
| `POST` | `/assist/chat` | Body: `department`, `ticket_id`, `employee_id`, `message`, `thread_id` opzionale |
| `GET`  | `/assist/thread` | Storico chat assist per tripla dept/ticket/employee + `thread_id` |

### Esempio intake (PowerShell)

```powershell
curl.exe -X POST http://127.0.0.1:8000/intake/chat -H "Content-Type: application/json" -d "{\"message\": \"Da fleet@trasportinord.it: urgenza tagliando Scudo FN445LM\"}"
```

### Esempio presa in carico

```powershell
curl.exe -X POST http://127.0.0.1:8000/departments/manutenzione/tickets/TICKET_UUID/accept -H "Content-Type: application/json" -d "{\"employee_id\": \"f3010101-1010-1010-1010-101010101012\"}"
```

### Esempio assist

```powershell
curl.exe -X POST http://127.0.0.1:8000/assist/chat -H "Content-Type: application/json" -d "{\"department\": \"manutenzione\", \"ticket_id\": \"...\", \"employee_id\": \"f3010101-1010-1010-1010-101010101012\", \"message\": \"Riassumi il ticket e i prossimi passi\"}"
```

---

## Memoria conversazione (checkpointer)

- **Intake:** chiave `inbox:{thread_id}` dove `thread_id` è quello restituito dall’API (o generato lato client).
- **Assist:** chiave `assist:{department}:{ticket_id}:{employee_id}:{thread_id}`.

`MemorySaver` è **volatile**: riavvio del server = perdita dello **stato LangGraph**; i **record su Postgres** (ticket, clienti, ecc.) restano.

---

## Dipendenti di esempio (seed)

| Reparto      | Nome            | `employee_id` |
|-------------|-----------------|---------------|
| vendita     | Paola Ricambi   | `f1010101-1010-1010-1010-101010101010` |
| vendita     | Marco Banco     | `f1020202-2020-2020-2020-202020202020` |
| acquisto    | Sara Acquisti   | `f2010101-1010-1010-1010-101010101011` |
| acquisto    | Luca Fornitori  | `f2020202-2020-2020-2020-202020202021` |
| manutenzione| Giulia Officina | `f3010101-1010-1010-1010-101010101012` |
| manutenzione| Davide Meccanico| `f3020202-2020-2020-2020-202020202022` |

---

## Workflow agente (5 fasi)

Intake e assist condividono lo stesso schema a fasi: **missione** → **ricognizione (tool)** → **ragionamento** → **azione (tool)** → **sintesi**. I tool differiscono (intake: anagrafica + apertura ticket smistato; assist: CRUD ticket sul reparto nel contesto).

Dettagli recenti intake:
- Titolo pratica normalizzato in formato coerente: **`[Reparto] Riassunto breve`** (es. `[Officina] ...`).
- Il riassunto titolo viene derivato dal **contesto completo** (`full_summary`), non solo dal primo messaggio.

---

## Risoluzione problemi

| Problema | Verifica |
|----------|----------|
| Errore connessione DB | `docker compose ps`; porte 5433–5435 libere; URL in `.env` |
| 401/403 Groq | Solo se `LLM_PROVIDER=groq`: chiave valida e `GROQ_MODEL` disponibile sul piano |
| Errore connessione Ollama | Ollama in esecuzione; `OLLAMA_BASE_URL` corretto; modello già `pull` |
| Assist 403/400 | Ticket accettato con lo **stesso** `employee_id`; stato `in_progress` |
| UI non carica | Avviare uvicorn dalla root progetto; cartella `static/` presente |

---

## Licenza / uso

POC interna/demo: non utilizzare in produzione senza hardening (auth, segreti, persistenza checkpoint, osservabilità).
