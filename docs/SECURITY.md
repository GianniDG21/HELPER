# Sicurezza — HELPER (POC)

Il prototipo è pensato per **rete locale / demo**; in esposizione su Internet servono contromisure aggiuntive oltre a quanto segue.

## Repository pubblico (es. GitHub)

Questo codice può stare su un repo **pubblico** solo se i segreti restano fuori dal versioning:

1. **Mai committare** `.env`, chiavi API (`GROQ_API_KEY`, `HELPER_API_KEY`, ecc.), certificati o JSON di service account. Il template sicuro è **`.env.example`** (solo placeholder o valori di demo documentati).
2. **Prima del primo push** (o dopo un commit accidentale): `git log -- .env` e, se necessario, [rimuovere i segreti dalla cronologia](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/removing-sensitive-data-from-a-repository); **ruotare** subito ogni chiave che sia mai entrata in un commit.
3. **Credenziali Postgres in `docker-compose.yml`** (`team` / `team`) sono **solo per demo locale**; per ambienti reali usare password forti e non versionare override con segreti (vedi `.gitignore` su `docker-compose.override.yml`).
4. Strumenti utili: [git-secrets](https://github.com/awslabs/git-secrets), [Gitleaks](https://github.com/gitleaks/gitleaks), o l’analisi “Secret scanning” di GitHub sul repo.

## Già disponibile nel codice

### Chiave API opzionale (`HELPER_API_KEY`)

Se in `.env` imposti **`HELPER_API_KEY`** (valore segreto sufficientemente lungo), le route REST **non pubbliche** richiedono lo stesso valore in:

- header **`X-API-Key: <valore>`**, oppure  
- **`Authorization: Bearer <valore>`**

**Esclusi** (sempre raggiungibili senza chiave): `/health`, `/`, `/ui/*`, `/docs`, `/redoc`, `/openapi.json`, `/favicon.ico`.

La UI statica sotto `/ui` può quindi essere servita senza chiave, mentre strumenti come curl/Postman verso `/intake`, `/assist`, `/departments`, `/pratiche` devono inviare la chiave **se** è configurata.

**Nota:** la chiave è condivisa da tutti i client; non sostituisce utenti individuali né OAuth.

### Controlli applicativi sui ticket

- Presa in carico, mail al richiedente, assist e chiusura pratica verificano **stato** e **assegnatario** (`employee_id` / UUID) lato server.
- I database reparto sono separati; il contesto reparto in query usa `set_team_id`.

## Cosa aggiungere per un ambiente più realistico

| Area | Azione tipica |
|------|----------------|
| **Autenticazione** | JWT o session per operatori; intake pubblico eventualmente con CAPTCHA / rate limit per IP. |
| **Autorizzazione** | Ruoli (solo reparto X; solo i propri ticket); oggi chi conosce UUID e API può chiamare. |
| **Trasporto** | **HTTPS** obbligatorio dietro reverse proxy (nginx, Caddy, cloud load balancer). |
| **Segreti** | Mai committare `.env`; usare vault o variabili ambiente injectate in CI/prod. |
| **Rate limiting** | Limitare `POST /intake/chat` e `POST /assist/chat` per IP/chiave (slowapi, reverse proxy). |
| **Header di sicurezza** | HSTS, `X-Content-Type-Options`, CSP sulla UI (config proxy). |
| **Dati personali** | GDPR: base giuridica, retention log, minimizzazione nei prompt inviati all’LLM. |
| **Supply chain** | `pip audit` / Dependabot; pin delle dipendenze in lockfile per rilasci. |
| **DB** | Password forti, rete privata tra app e Postgres, backup crittografati. |

## Test automatici

La suite di default **non** imposta `HELPER_API_KEY` così i test restano semplici. In CI con chiave attiva andrebbero aggiunti test che passano l’header atteso.
