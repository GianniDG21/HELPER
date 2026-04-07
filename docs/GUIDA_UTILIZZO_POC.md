# Guida all’utilizzo — POC helpdesk multi-reparto

Questa guida descrive **come usare la POC** in demo o in prova locale: interfaccia web, flusso operativo consigliato, dati di esempio e messaggi di errore frequenti.

Per una versione **solo operativa** (senza dettagli tecnici in interfaccia) vedi anche [MANUALE_OPERATIVO.md](MANUALE_OPERATIVO.md) e l’URL **/ui/clean.html**.

## Cosa dimostra la POC

- Un **canale unico** (messaggio tipo email) arriva alla centrale: l’agente **capisce la richiesta**, interroga **anagrafica** e **elenchi reparti**, e apre la pratica dopo **email**, **nome referente** e i **dati operativi minimi** (es. **anno e km** per interventi su veicolo, **quantità** per ricambi; per richieste d’ufficio basta una descrizione sufficiente). È presente una **guardia server-side**: senza dati minimi il ticket non viene aperto anche se il modello prova a chiamare il tool.
- La pratica resta in **coda “in attesa”** finché un **dipendente non la prende in carico**.
- Solo dopo la presa in carico, il dipendente può **chattare** con un assistente che legge/aggiorna i dati **solo del suo reparto**.

Non è un prodotto finito: memoria conversazione in RAM, niente autenticazione utente. In UI puoi scegliere il modello **Locale (Ollama)** o **Remoto (Groq)** dall’header.

---

## Primo avvio (ordine consigliato)

1. **Clona / apri il progetto** e crea l’ambiente Python (es. `python -m venv .venv`).
2. **Configura `.env`** da `.env.example`: con **Ollama** (default) avvia Ollama e `ollama pull` sul modello in `OLLAMA_MODEL`; con **Groq** imposta `LLM_PROVIDER=groq` e `GROQ_API_KEY`.
3. **Installa dipendenze**: `pip install -r requirements.txt`.
4. **Avvia tutto in un colpo** (consigliato dopo il primo setup): dalla root del repo, **Windows** `.\scripts\start.ps1`, **Linux/macOS** `./scripts/start.sh` — esegue `docker compose up -d` (quattro Postgres su host **6433**–**6436**) e poi **uvicorn** sulla porta **8000** (sovrascrivibile con `HELPER_PORT`). Dettagli nel [README](../README.md#avvio-applicazione).
5. In alternativa, passo passo: **`docker compose up -d`** poi **`uvicorn app.main:app --reload --host 0.0.0.0 --port 8000`** (con venv attivo).
6. **Apri l’interfaccia**: nel browser vai a **http://127.0.0.1:8000/ui/**

Se cambi gli script SQL e vuoi ricreare i DB da zero: `docker compose down -v` poi di nuovo `docker compose up -d` (o di nuovo lo script di start).

---

## Interfaccia web (`/ui/`)

### Tab **1 · Richiesta** (intake / “cliente”)

- Simula l’**arrivo di una richiesta** (testo libero, come fosse il corpo di una mail).
- L’agente risponde in chat; quando la richiesta è completa, nella risposta comparirà un **codice pratica** (UUID) e il **reparto** di destinazione.
- Se l’agente ha effettivamente aperto la pratica (`route_and_open_ticket`), l’API restituisce **`routed_department`** e **`ticket_id`**: in background vengono compilati **reparto** e **codice pratica** per il tab Dipendente **senza** cambiare tab (resti sulla chat richiesta). Alla prima apertura del tab Dipendente con quel reparto, l’elenco **Pratiche in attesa** può aggiornarsi automaticamente.
- Sotto la chat, la sezione collassabile **«Cosa è successo dietro le quinte»** mostra, in linguaggio semplice, i passaggi (verifica anagrafica, caricamento reparti, apertura ticket). I dettagli tecnici (JSON) sono espandibili.

**Suggerimento per la demo:** con email e nome nel modulo, un dominio tipo `trasportinord.it` o `disbrigo.it` fa vedere l’**anagrafica** in azione; per il reparto manutenzione ricorda **km** (e anno/modello se mancano).

Il pulsante **Pulisci** (tab Richiesta) azzera la conversazione salvata nel browser.

### Tab **2 · Dipendente**

1. Dopo un intake andato a buon fine, **reparto** e **codice pratica** sono già impostati (valori del tool). La pratica resta in **pending_acceptance** finché non la prendi in carico. In alternativa: **Pratiche in attesa** → **Usa**.
2. Scegli **Dipendente** dal menu a tendina (nomi caricati da `GET /departments/{reparto}/employees`). L’assegnazione la confermi con **Prendi in carico**.
3. Clicca **Prendi in carico**: se va a buon fine, lo stato della pratica diventa adatto alla chat.
4. Usa la **Chat dipendente** per domande operative (riepilogo ticket, clienti, aggiornamento stato, ecc.).
5. Nel blocco **Messaggio al richiedente**, l’oggetto viene proposto automaticamente in base al contesto pratica selezionata (modificabile).

Anche qui è disponibile il pannello **dietro le quinte** per l’ultimo turno.

---

## Flusso demo in 5 minuti

| Passo | Azione |
|------|--------|
| 1 | Tab **Richiesta**: modulo **nome/cognome/email** e messaggio con **tutti i dati utili** (es. ordine B2B: *«Sono Mario Ronchi, problema ordine 998…»*; officina: *«Tagliando Polo 2018, km 72.000»*). |
| 2 | Se manca qualcosa, rispondi alle **singole** domande dell’agente. |
| 3 | Con **codice pratica** e reparto (es. acquisto), puoi restare sulla richiesta o aprire **Dipendente** (campi già compilati). |
| 4 | Tab **Dipendente**: menu **Dipendente** → es. **Sara Acquisti** o **Luca Fornitori**; verifica **Pratiche in attesa** se serve. |
| 5 | **Prendi in carico** → chat: *«Riassumi la pratica e prossimi passi»*. |

---

## Email e aziende di esempio (anagrafica)

L’intake collega il **dominio email** alle aziende seed. Esempi (estratto concettuale; vedi `app/intake/companies_registry.py` per l’elenco completo):

| Dominio tipico | Reparto suggerito (indicativo) |
|----------------|--------------------------------|
| `trasportinord.it` | officina (`manutenzione` lato API) |
| `disbrigo.it` | acquisto |
| `garino-officina.it` / `email.it` | vendita |

Se il dominio non è in anagrafica, lo smistamento si basa comunque sul **testo** della richiesta.

---

## ID dipendenti di prova (seed)

Usare **nel tab Dipendente** il campo «Tu (dipendente)». Elenco completo nella tabella **Dipendenti di esempio** nel [README](../README.md).

Regola: il dipendente deve **appartenere allo stesso reparto** del database su cui è stata aperta la pratica (vendita / acquisto / officina, chiave API `manutenzione`).

---

## Messaggi di errore comuni (tab Dipendente)

| Messaggio (API) | Causa | Cosa fare |
|-----------------|-------|-----------|
| Ticket non trovato | UUID sbagliato o reparto errato | Verifica reparto e codice incollato dall’intake |
| Dipendente non trovato | UUID inesistente o reparto sbagliato | Usa un `employee_id` del reparto corretto dal README |
| Il ticket non è assegnato a questo dipendente | Hai usato un altro dipendente o non hai accettato | **Prendi in carico** con lo **stesso** ID usato in chat |
| Il ticket deve essere accettato (`in_progress`) | Pratica ancora in coda | Esegui **Prendi in carico** prima della chat |

---

## Uso senza interfaccia (curl / strumenti HTTP)

Esempi minimali nel [README](../README.md): `POST /intake/chat`, `GET` coda pending, `POST .../accept`, `POST /assist/chat`.  
La documentazione interattiva OpenAPI è su **http://127.0.0.1:8000/docs** con l’API avviata.

---

## Limiti noti della POC

- **Checkpointer in memoria** (`MemorySaver`): al riavvio del processo `uvicorn` le conversazioni LangGraph si perdono; i **ticket su Postgres** restano.
- Nessun login: chiunque raggiunga l’URL può chiamare l’API (adatta solo a rete locale / demo).
- Rate limit e disponibilità modelli dipendono da **Groq** e dalla chiave API.
- Lo smistamento usa la chiave reparto `manutenzione` lato API/DB, ma in UI è mostrato come **officina**.
- I titoli pratica intake sono normalizzati in formato coerente: **`[Reparto] Riassunto breve`** (derivato dal contesto completo, non dal primo messaggio).

---

## Dove approfondire

- **[Inventario dati DB (seed)](DATI_DATABASE_POC.md)**: UUID di companies, employees, customers, ticket di esempio per reparto.
- **README del progetto**: setup, variabili d’ambiente, elenco endpoint, tabella dipendenti.
- Codice grafi: `app/agent/intake_graph.py`, `app/agent/assist_graph.py`.
- Prompt e comportamento agente: `app/agent/intake_prompts.py`, `app/agent/assist_prompts.py`.


## Prompt iniziali d'esempio

Copiali nel tab **Richiesta** dopo aver compilato nome/cognome/email.

- **Officina (completo, apre pratica):**  
  `Buongiorno, ho un problema al furgone Ducato 2019 targa AB123CD, 98000 km: perdita olio e rumore freni anteriori.`

- **Officina (incompleto, deve chiedere dettaglio):**  
  `Buongiorno, ho un problema con il furgone.`  
  (atteso: richiesta di km e identificativo veicolo)

- **Ricambi (completo, apre pratica):**  
  `Ci servono 12 filtri olio codice FO-778 per la flotta, consegna urgente entro venerdì.`

- **Ricambi (incompleto, deve chiedere quantità):**  
  `Dobbiamo ordinare filtri olio codice FO-778.`  
  (atteso: richiesta quantità)

- **Acquisto/Ufficio (B2B):**  
  `Segnalo incongruenza IVA sulla fattura 45 relativa all'ordine 998; serve verifica amministrativa con il fornitore.`

- **Vendita:**  
  `Richiedo supporto commerciale per preventivo rinnovo flotta aziendale con 6 veicoli, consegna Q3.`