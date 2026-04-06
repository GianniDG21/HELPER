# Manuale operativo — HELPER (POC officina)

Questa guida è pensata per **chi usa l’interfaccia web** in demo o prova, senza entrare nei dettagli tecnici. Per installazione, API e database vedi il [README](../README.md) e la [guida passo-passo](GUIDA_UTILIZZO_POC.md).

---

## Due modi di usare la schermata

| Vista | Come aprirla | Contenuto |
|--------|----------------|-----------|
| **Pulita** | Da browser: **http://127.0.0.1:8000/ui/clean.html** oppure **http://127.0.0.1:8000/ui/index.html?clean=1** | Solo testi per l’utente: niente riferimenti ad API, endpoint o traccia tecnica nascosta dove possibile. |
| **Tecnica** | **http://127.0.0.1:8000/ui/** (predefinita) | Traccia dei passaggi, pannello “Esito API”, debug server se attivo, suggerimenti con nomi di servizi. |

Puoi passare dall’una all’altra con i link in alto a destra nell’intestazione.

---

## Ruolo 1 — Richiedente (tab **Richiesta**)

### Cosa serve
- **Nome**, **cognome** e **email** compilati **prima** di ogni invio (sono obbligatori insieme).
- Un messaggio chiaro su cosa ti serve (es. ordine, veicolo/tagliando, ricambi, urgenza).

### Informazioni che il sistema deve avere in modo esplicito (prima di aprire la pratica)

Allineato al **gate apertura pratica** dell’assistente (nessun ticket finché non sono coperti i punti pertinenti alla tua richiesta):

| Area | Cosa deve risultare chiaro |
|------|----------------------------|
| **Contatti** | **Email** (indirizzo valido, nel modulo o nel testo). **Nome e cognome** del referente (nel modulo in alto **oppure** scritti nel messaggio — non bastano da soli nome azienda o ragione sociale da anagrafica). |
| **Veicolo / officina** (tagliando, revisione, guasto, intervento, ecc.) | **Chilometraggio attuale** e **identificativo del veicolo**: **targa** (es. formato italiano) **oppure** modello con **anno** (es. *Polo 2018*). Se nel messaggio c’è già targa o anno/modello, l’assistente chiederà in genere **solo i km**; se ci sono già i km, chiederà **solo** targa o anno/modello. |
| **Ricambi / materiale** | Oltre a descrizione o codice (se servono), la **quantità** (numero di pezzi). Se manca solo quella, ti verrà chiesta **solo** la quantità. |
| **Ufficio / B2B** (fatture, ordini, segnalazioni «per conto di…») | **Non** serve una generica «autorizzazione» a inoltrare: bastano contatti (sopra) e una **descrizione sufficiente** del problema o della pratica amministrativa. |

Se la richiesta riguarda **contemporaneamente** veicolo e ricambi, il sistema si aspetta di poter desumere dal filo della conversazione **tutti** i requisiti pertinenti (in linea con le euristiche operative del POC: identità veicolo + km ove richiesto, e quantità ove richiesta per i pezzi).

### Come scrivere
- **Invio** sulla tastiera invia il messaggio (come il pulsante “Invia”).
- **Maiuscole + Invio** va a capo nel testo.

### Cosa aspettarti
- L’assistente può fare **una domanda alla volta** per completare i **dati utili al reparto** (es. per un’auto: **chilometraggio** se hai già indicato anno o modello; per ricambi: **quantità**). **Non** ti chiederà una generica «autorizzazione» per aprire il ticket: il messaggio che invii è già la richiesta.
- Quando la pratica è stata **registrata**, nel pannello a destra (**Stato della pratica** in vista pulita, **Esito API** in vista tecnica) compaiono il **numero pratica** e il **reparto**; sono quelli da considerare attendibili, non eventuali numeri citati solo nel testo della chat.
- In basso a destra puoi **aggiornare i messaggi** inviati dal reparto verso la tua email (simulazione): compaiono come nel mondo reale una volta che un operatore ti ha scritto.

### Esempio (richiesta acquisti)
1. Nome `Laura`, cognome `Bianchi`, email `laura@fornitore.it`.
2. Messaggio: *«Buongiorno, segnaliamo un errore IVA sulla fattura 45 riferita all’ordine 778. Siamo il reparto acquisti di Ricambi Nord.»*
3. Se manca un dettaglio operativo (es. quantità per un ordine ricambi), rispondi con **un solo dato** alla volta.
4. Quando compare il numero pratica nel riepilogo a destra, la richiesta è in coda al reparto corretto.

### Esempio (officina / veicolo)
1. Dati anagrafici compilati.
2. *«Devo il tagliando per la mia VW Polo 2018.»* — se l’assistente chiede ancora qualcosa, di solito sarà il **chilometraggio attuale** (hai già l’anno nel testo).
3. Alternativa: *«Intervento sul furgone targato AB123CD: perdita olio, urgente per domani, 95.000 km.»* con anno o targa e km già chiari.
4. Rispondi alle domande finché nel riepilogo compare numero pratica e reparto.

---

## Ruolo 2 — Dipendente (tab **Dipendente**)

### Preparazione
1. **Reparto** (opzionale come filtro): puoi lasciare **«Tutti i reparti (vista unificata)»** per un unico elenco di tutte le pratiche; oppure filtrare per **vendita**, **acquisto** o **manutenzione**.
2. Scegli **te stesso** nel menu **Operatore** (compare dopo aver scelto un reparto, oppure dopo aver cliccato una riga in vista unificata — così il menu si aggiorna sul reparto della pratica).

### Elenco pratiche
- Clicca **Aggiorna elenco pratiche**: con un reparto selezionato vedi **tutte** le pratiche di quel reparto; in **vista unificata** vedi le pratiche di **tutti** i reparti, con colonna **Reparto**, oltre a stato, titolo, richiedente e assegnatario.
- **Clic su una riga** (o scelta dal menu «Pratica selezionata»): in vista unificata il sistema imposta il **reparto** della pratica per abilitare operatore e azioni.
- Sopra l’elenco, un riepilogo indica quante richieste sono ancora **in attesa** in officina; in vista per singolo reparto indica anche quante sono in coda in quel reparto.

### Prendere in carico
1. Seleziona una riga con stato **In coda** (o scegli la stessa pratica dal menu “Pratica selezionata”).
2. Assicurati che l’operatore selezionato sia **tu**.
3. Clicca **Prendi in carico**: la pratica passa a **In lavorazione** e resta assegnata a te.

### Scrivere al richiedente
- Dopo la presa in carico, se la pratica è **tua**, il blocco **Messaggio al richiedente** si abilita.
- Compila **oggetto** e **testo**; **Invio** invia (come il pulsante). Il richiedente vede il messaggio nel tab Richiesta, area messaggi dal reparto.
- Funziona solo se sei l’**assegnatario** della pratica selezionata.

### Chiudere la pratica
- Quando la pratica è **In lavorazione** e **assegnata a te**, il pulsante **Chiudi pratica (risolto)** si abilita.
- La chiusura aggiorna lo stato a **risolto** sul registry e sul ticket di reparto (in demo non invia email automatica al richiedente: se serve un ultimo messaggio, usalo prima dalla sezione **Messaggio al richiedente**).

### Assistente per il reparto
- Sotto, la **chat** parla con l’assistente che può usare i dati del ticket del reparto (dopo presa in carico).
- **Invio** invia; **Maiuscole + Invio** a capo.
- **Nuovo thread chat** azzera solo la conversazione con l’assistente per quella combinazione reparto / pratica / operatore, senza cancellare il ticket.

### Esempio (operatore acquisti)
1. Reparto **acquisto**, operatore **Sara Acquisti** (o altro utente seed del reparto).
2. Aggiorna elenco: scegli pratica **In coda** legata alla segnalazione fornitore.
3. **Prendi in carico**.
4. In **Messaggio al richiedente**: oggetto *«Ricevuta segnalazione fattura 45»*, testo *«Stiamo verificando con amministrazione e ti aggiorniamo entro 24 ore.»*
5. Opzionale: in chat assistente, *«Riassumi la pratica e prossimi passi.»*

---

## Suggerimenti pratici

- Se il richiedente non vede aggiornamenti, verifica che abbia ancora aperto il tab **Richiesta** con gli stessi dati anagrafici e, se serve, che aggiorni i messaggi dal reparto.
- Se l’elenco filtrato per reparto è vuoto ma il riepilogo dice che ci sono richieste in attesa, prova la **vista unificata** (**Tutti i reparti**) oppure **cambia reparto**: la pratica può essere in un altro settore.
- Dopo un **riavvio del server** la memoria della chat dell’assistente può azzerarsi, ma le pratiche su database restano: usa **Aggiorna elenco** e riseleziona la pratica.

---

## Dove approfondire

| Documento | Contenuto |
|-------------|-----------|
| [README](../README.md) | Stack, Docker, variabili d’ambiente, tabella API, troubleshooting |
| [GUIDA_UTILIZZO_POC.md](GUIDA_UTILIZZO_POC.md) | Flusso dettagliato POC, note su thread e UI |
| [DATI_DATABASE_POC.md](DATI_DATABASE_POC.md) | Seed, UUID dipendenti e dati di esempio |
