# Export - Modular Ticket Agent (LangGraph + LangChain)

Questa cartella contiene una versione **modulare** dell'agente ticketing, pensata per essere riusata e personalizzata senza vincoli sul dominio officina.

## Obiettivo

- mantenere il loop agente con LangGraph/LangChain
- mantenere il comportamento ticketing (raccolta dati + apertura ticket)
- permettere sostituzione rapida del backend ticket (stub o Zammad)

## Struttura

- `core/`
  - `generic_engine.py`: motore LangGraph a 5 fasi (mission -> scan -> think -> act -> learn)
  - `settings.py`: configurazione runtime (provider LLM, backend ticket, Zammad)
  - `llm_factory.py`: inizializzazione LLM (`ollama` o `groq`)
- `integrations/`
  - `zammad_client.py`: client HTTP minimale verso API Zammad
- `modules/ticketing/`
  - `prompts.py`: prompt neutri per intake ticket
  - `tools.py`: read/write tools con adapter backend
  - `graph.py`: wiring modulo ticketing sul core engine
- `app.py`: endpoint FastAPI di esempio (`POST /chat`)
- `.env.example`: configurazione base
- `requirements.txt`: dipendenze minime

## Backends ticket supportati

- `TICKETING_BACKEND=stub`: non apre ticket reali, utile in setup iniziale
- `TICKETING_BACKEND=zammad`: crea ticket su Zammad usando API token

## Configurazione rapida

1. Copia env:

```powershell
Copy-Item export/.env.example export/.env
```

2. Imposta provider LLM:

- locale: `LLM_PROVIDER=ollama`
- cloud: `LLM_PROVIDER=groq` + `GROQ_API_KEY`

3. Se usi Zammad:

- `TICKETING_BACKEND=zammad`
- `ZAMMAD_BASE_URL=http://localhost:8080` (o URL istanza)
- `ZAMMAD_API_TOKEN=...`
- `ZAMMAD_CUSTOMER=customer@example.com`
- `ZAMMAD_GROUP=Users`

4. Avvio:

```powershell
cd export
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app:app --reload --host 0.0.0.0 --port 8010
```

Test:

```powershell
curl.exe -X POST http://127.0.0.1:8010/chat -H "Content-Type: application/json" -d "{\"message\":\"Ho bisogno di assistenza per un ordine urgente\"}"
```

## Note

- Il modulo e volutamente neutro: campi richiesti e regole possono essere cambiati in `modules/ticketing/tools.py`.
- Per dominio specifico (officina, retail, IT support), modifica prompt e policy senza cambiare `core/generic_engine.py`.
