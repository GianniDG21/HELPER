(function () {
  "use strict";

  var H_CLEAN = /(?:^|[?&])clean=1(?:&|$)/.test(location.search);
  if (H_CLEAN) {
    document.documentElement.classList.add("helper-clean");
    var appTitle = document.getElementById("app-title");
    if (appTitle) appTitle.textContent = "HELPER · Assistenza officina";
  }

  /* --- API (allineata a app/main.py) --- */
  const LS_IN_THREAD = "helper_in_thread";
  const LS_LAST_TICKET = "helper_last_ticket";
  const LS_LAST_DEPT = "helper_last_dept";
  const LS_CONTACT = "helper_contact_json";
  /** Ultimo turno intake: snapshot da POST /intake/chat (passaggio verso operatore). */
  const SS_INTAKE_HANDOFF = "helper_intake_handoff_v1";
  const SS_LAST_INTAKE_TRACE = "helper_last_intake_trace_v1";
  const SS_LAST_INTAKE_DEBUG = "helper_last_intake_debug_v1";

  function assistStorageKey(dept, ticketId, empId) {
    return "helper_asst_" + dept + "_" + ticketId + "_" + empId;
  }

  async function apiFetch(method, url, jsonBody) {
    const opts = { method, headers: {} };
    if (jsonBody !== undefined) {
      opts.headers["Content-Type"] = "application/json";
      opts.body = JSON.stringify(jsonBody);
    }
    const r = await fetch(url, opts);
    const text = await r.text();
    let data = {};
    try { data = text ? JSON.parse(text) : {}; } catch (_) { data = { _raw: text }; }
    if (!r.ok) {
      const det = data.detail;
      const msg = typeof det === "string" ? det : (Array.isArray(det) ? det.map(function (x) { return x.msg || JSON.stringify(x); }).join("; ") : JSON.stringify(data));
      throw new Error(msg || ("HTTP " + r.status));
    }
    return data;
  }

  function esc(s) {
    const d = document.createElement("div");
    d.textContent = s == null ? "" : String(s);
    return d.innerHTML;
  }

  function setTab(which) {
    var vin = document.getElementById("view-in");
    var vop = document.getElementById("view-op");
    var tin = document.getElementById("tab-in");
    var top = document.getElementById("tab-op");
    var isIn = which === "in";
    vin.classList.toggle("is-on", isIn);
    vop.classList.toggle("is-on", !isIn);
    vin.removeAttribute("hidden");
    vop.removeAttribute("hidden");
    vin.setAttribute("aria-hidden", isIn ? "false" : "true");
    vop.setAttribute("aria-hidden", isIn ? "true" : "false");
    tin.setAttribute("aria-selected", isIn);
    top.setAttribute("aria-selected", !isIn);
  }

  document.getElementById("tab-in").addEventListener("click", function () { setTab("in"); });
  document.getElementById("tab-op").addEventListener("click", function () {
    setTab("op");
    opOnShow().catch(function (e) {
      setSt("st-op", "Errore caricamento: " + (e && e.message ? e.message : String(e)), "err");
    });
  });

  function wireBtnToOperator() {
    setTab("op");
    syncOperatorMaskFromHandoff()
      .then(function () {
        return opLoadThread();
      })
      .then(function () {
        setSt("st-op", H_CLEAN ? "Reparto aggiornato in base all’ultima richiesta." : "Maschera allineata all’ultimo esito API (Richiesta).", "ok");
      })
      .catch(function (e) {
        setSt("st-op", (e && e.message) ? e.message : String(e), "err");
      });
  }

  document.getElementById("btn-to-operator").addEventListener("click", wireBtnToOperator);
  var btnToOpClean = document.getElementById("btn-to-operator-clean");
  if (btnToOpClean) btnToOpClean.addEventListener("click", wireBtnToOperator);
  var inInboxClean = document.getElementById("in-inbox-refresh-clean");
  if (inInboxClean) inInboxClean.addEventListener("click", function () {
    refreshInbox();
  });

  /* --- Intake --- */
  function readContact() {
    return {
      contact_first_name: document.getElementById("in-fn").value.trim(),
      contact_last_name: document.getElementById("in-ln").value.trim(),
      contact_email: document.getElementById("in-em").value.trim()
    };
  }

  function persistContact() {
    try { localStorage.setItem(LS_CONTACT, JSON.stringify(readContact())); } catch (e) {}
  }

  function loadContact() {
    try {
      var j = JSON.parse(localStorage.getItem(LS_CONTACT) || "{}");
      if (j.contact_first_name) document.getElementById("in-fn").value = j.contact_first_name;
      if (j.contact_last_name) document.getElementById("in-ln").value = j.contact_last_name;
      if (j.contact_email) document.getElementById("in-em").value = j.contact_email;
    } catch (e) {}
  }

  ["in-fn", "in-ln", "in-em"].forEach(function (id) {
    var el = document.getElementById(id);
    if (el) el.addEventListener("blur", persistContact);
  });

  function bubble(container, who, text, isUser) {
    var d = document.createElement("div");
    d.className = "bubble " + (isUser ? "u" : "a");
    d.innerHTML = "<div class='who'>" + esc(who) + "</div><div>" + esc(text).replace(/\n/g, "<br/>") + "</div>";
    container.appendChild(d);
    container.scrollTop = container.scrollHeight;
  }

  function traceRender(el, steps) {
    el.innerHTML = "";
    if (!steps || !steps.length) {
      el.innerHTML = "<p style='color:var(--muted);margin:0'>Nessun passaggio.</p>";
      return;
    }
    steps.forEach(function (s) {
      var pre = document.createElement("pre");
      pre.style.whiteSpace = "pre-wrap";
      pre.style.margin = "0 0 0.5rem";
      pre.style.fontSize = "0.72rem";
      pre.style.color = "var(--muted)";
      var title = (s.ui && s.ui.title) ? s.ui.title : s.kind;
      var sum = (s.ui && s.ui.summary) ? s.ui.summary : (s.content || "");
      pre.textContent = title + "\n" + sum;
      el.appendChild(pre);
    });
  }

  function setSt(id, text, cls) {
    var e = document.getElementById(id);
    e.textContent = text;
    e.className = "status" + (cls ? " " + cls : "");
  }

  function _validDept(d) {
    return d && ["vendita", "acquisto", "manutenzione"].indexOf(d) >= 0;
  }

  /** Confronto UUID case-insensitive (select vs API). */
  function normEmpId(s) {
    if (s == null || s === "") return "";
    return String(s).trim().toLowerCase();
  }

  function empIdsMatch(a, b) {
    return normEmpId(a) !== "" && normEmpId(a) === normEmpId(b);
  }

  /** Se la pratica ha un assegnatario, seleziona quel dipendente nel menu (se presente nell’elenco). */
  function syncOperatorToAssignee() {
    var meta = getSelectedPraticaMeta();
    var sel = document.getElementById("op-emp");
    if (!meta || !meta.assigned_to || !sel) return;
    var want = normEmpId(meta.assigned_to);
    if (!want) return;
    for (var i = 0; i < sel.options.length; i++) {
      var o = sel.options[i];
      if (normEmpId(o.value) === want) {
        sel.value = o.value;
        return;
      }
    }
  }

  /** Reparto effettivo per API: menu reparto oppure reparto della pratica selezionata (vista unificata). */
  function operatorEffectiveDept() {
    var d = document.getElementById("op-dept").value;
    if (_validDept(d)) return d;
    var m = getSelectedPraticaMeta();
    return m && _validDept(m.department) ? m.department : "";
  }

  function snapshotFromIntakeResponse(d) {
    var tid = d.ticket_id != null && d.ticket_id !== "" ? String(d.ticket_id).trim() : null;
    var dept = d.routed_department != null && d.routed_department !== "" ? String(d.routed_department).trim() : null;
    return {
      thread_id: d.thread_id || null,
      ticket_id: tid && /^\d+$/.test(tid) ? tid : null,
      routed_department: _validDept(dept) ? dept : null,
      at: new Date().toISOString()
    };
  }

  function saveIntakeHandoff(snap) {
    try { sessionStorage.setItem(SS_INTAKE_HANDOFF, JSON.stringify(snap)); } catch (e) {}
    if (snap.ticket_id) {
      try {
        localStorage.setItem(LS_LAST_TICKET, snap.ticket_id);
        if (snap.routed_department) localStorage.setItem(LS_LAST_DEPT, snap.routed_department);
      } catch (e2) {}
    }
  }

  function loadIntakeHandoff() {
    try {
      var raw = sessionStorage.getItem(SS_INTAKE_HANDOFF);
      return raw ? JSON.parse(raw) : null;
    } catch (e) {
      return null;
    }
  }

  /** Dopo refresh pagina lo snapshot in session è vuoto: ricostruisci da localStorage se possibile. */
  function restoreHandoffSnapshotIfNeeded() {
    if (loadIntakeHandoff()) return;
    var t = localStorage.getItem(LS_LAST_TICKET);
    var d = localStorage.getItem(LS_LAST_DEPT);
    if (t && /^\d+$/.test(t)) {
      try {
        sessionStorage.setItem(
          SS_INTAKE_HANDOFF,
          JSON.stringify({
            thread_id: localStorage.getItem(LS_IN_THREAD),
            ticket_id: t,
            routed_department: _validDept(d) ? d : null,
            at: new Date().toISOString()
          })
        );
      } catch (e) {}
    }
  }

  /**
   * Dopo reload (browser o uvicorn): se manca il reparto, lo chiede al server;
   * così Esito API / banner / coda restano allineati ai ticket reali nel DB.
   */
  async function reconcileHandoffWithServer() {
    var snap = loadIntakeHandoff();
    var tid = (snap && snap.ticket_id) || localStorage.getItem(LS_LAST_TICKET);
    if (!tid || !/^\d+$/.test(String(tid))) return;
    var deptOk = snap && _validDept(snap.routed_department);
    if (deptOk) return;
    try {
      var loc = await apiFetch("GET", "/tickets/" + encodeURIComponent(tid) + "/department");
      if (!loc || !_validDept(loc.department)) return;
      var merged = snap
        ? Object.assign({}, snap, { routed_department: loc.department, ticket_id: String(tid) })
        : {
            thread_id: localStorage.getItem(LS_IN_THREAD),
            ticket_id: String(tid),
            routed_department: loc.department,
            at: new Date().toISOString()
          };
      saveIntakeHandoff(merged);
      try {
        localStorage.setItem(LS_LAST_DEPT, loc.department);
      } catch (e) {}
    } catch (e) {}
  }

  function renderIntakeOutcomePanel() {
    var wrap = document.getElementById("in-api-outcome");
    var body = document.getElementById("in-api-outcome-body");
    var snap = loadIntakeHandoff();
    if (!snap || !snap.at) {
      wrap.className = "api-outcome muted";
      body.innerHTML = "Nessun dato ancora: invia un messaggio dalla tab Richiesta.";
      return;
    }
    if (snap.ticket_id && snap.routed_department) {
      wrap.className = "api-outcome ok";
      body.innerHTML =
        "Pratica registrata: <strong>#" + esc(snap.ticket_id) + "</strong> · reparto <strong>" + esc(snap.routed_department) + "</strong>" +
        (!H_CLEAN && snap.thread_id
          ? "<br/><span style='color:var(--muted);font-size:0.72rem'>thread " + esc(snap.thread_id.slice(0, 8)) + "…</span>"
          : "");
      return;
    }
    if (snap.ticket_id) {
      wrap.className = "api-outcome ok";
      body.innerHTML = H_CLEAN
        ? "Pratica <strong>#" + esc(snap.ticket_id) + "</strong> — per il reparto usa il pulsante «Vai al reparto» o apri il tab Dipendente."
        : "Pratica <strong>#" + esc(snap.ticket_id) + "</strong> (reparto da confermare con «Apri tab Dipendente…»).";
      return;
    }
    wrap.className = "api-outcome warn";
    body.innerHTML = H_CLEAN
      ? "<strong>La pratica non risulta ancora registrata</strong> dal sistema in questo scambio. Non fare affidamento su numeri citati solo nella chat finché non compaiono qui."
      : "<strong>Nessuna pratica aperta</strong> dall’API in questo turno. " +
        "Ignora eventuali «numeri pratica» scritti dall’assistente nella chat: non sono validi finché non compaiono qui.";
  }

  function updateOperatorHandoffBanner() {
    var el = document.getElementById("op-handoff-banner");
    var snap = loadIntakeHandoff();
    if (snap && snap.ticket_id && snap.routed_department) {
      el.className = "op-banner is-on";
      el.innerHTML = H_CLEAN
        ? "Ultima richiesta registrata: pratica <strong>#" + esc(snap.ticket_id) + "</strong>, reparto <strong>" + esc(snap.routed_department) + "</strong>. Apri il tab Dipendente e aggiorna l’elenco."
        : "Ultima pratica da intake: <strong>#" + esc(snap.ticket_id) + "</strong> · <strong>" + esc(snap.routed_department) +
          "</strong> — usa <strong>Apri tab Dipendente e allinea elenco</strong> dalla Richiesta oppure <strong>Aggiorna elenco pratiche</strong> qui.";
      return;
    }
    if (snap && snap.ticket_id) {
      el.className = "op-banner is-on";
      el.innerHTML = H_CLEAN
        ? "Ultima pratica: <strong>#" + esc(snap.ticket_id) + "</strong>. Apri il tab Dipendente e aggiorna l’elenco per vedere il reparto."
        : "Ultima pratica da intake: <strong>#" + esc(snap.ticket_id) + "</strong> (reparto: allinea con Aggiorna elenco o dalla Richiesta).";
      return;
    }
    el.className = "op-banner";
    el.innerHTML = "";
  }

  /**
   * Sincronizza reparto, coda e menu pratica dal sessionStorage (e da GET /tickets/{id}/department se serve).
   */
  async function syncOperatorMaskFromHandoff() {
    var snap = loadIntakeHandoff();
    var dept = snap && snap.routed_department;
    var tid = snap && snap.ticket_id;
    if (tid && !dept) {
      try {
        var loc = await apiFetch("GET", "/tickets/" + encodeURIComponent(tid) + "/department");
        if (loc && _validDept(loc.department)) dept = loc.department;
      } catch (e) {}
    }
    if (_validDept(dept)) {
      document.getElementById("op-dept").value = dept;
      try { localStorage.setItem(LS_LAST_DEPT, dept); } catch (e) {}
    }
    await loadEmployees();
    document.getElementById("op-ticket").value = "";
    var n = await loadPraticheElenco();
    if (tid) {
      var sel = document.getElementById("op-ticket");
      if (!Array.from(sel.options).some(function (o) { return o.value === tid; })) {
        var o = document.createElement("option");
        o.value = tid;
        o.textContent = tid + " — (da intake, aggiorna elenco se manca)";
        sel.appendChild(o);
      }
      sel.value = tid;
      opHighlightRow(tid);
      updateOpMailPanel();
    }
    updateOperatorHandoffBanner();
    return n;
  }

  async function loadInThread() {
    var tid = localStorage.getItem(LS_IN_THREAD);
    var chat = document.getElementById("chat-in");
    chat.innerHTML = "";
    if (!tid) {
      setSt("st-in", "Nessun thread salvato.", "");
      return;
    }
    try {
      var d = await apiFetch("GET", "/intake/thread?thread_id=" + encodeURIComponent(tid));
      (d.messages || []).forEach(function (m) {
        if (m.role === "user") bubble(chat, "Tu", m.content, true);
        else if (m.role === "assistant") bubble(chat, "Assistente", m.content, false);
      });
      setSt("st-in", "Thread " + tid.slice(0, 8) + "…", "ok");
    } catch (err) {
      setSt("st-in", String(err.message), "err");
    }
  }

  document.getElementById("in-send").addEventListener("click", async function () {
    var c = readContact();
    if (!c.contact_first_name || !c.contact_last_name || !c.contact_email) {
      setSt("st-in", "Compilare nome, cognome e email.", "err");
      return;
    }
    var msg = document.getElementById("in-msg").value.trim();
    if (!msg) return;
    var tid = localStorage.getItem(LS_IN_THREAD);
    /** @type {Record<string, string>} */
    var body = Object.assign({ message: msg }, c);
    if (tid) body.thread_id = tid;

    setSt("st-in", "Elaborazione…", "load");
    document.getElementById("in-send").disabled = true;
    var chat = document.getElementById("chat-in");
    bubble(chat, "Tu", msg, true);
    document.getElementById("in-msg").value = "";

    try {
      var d = await apiFetch("POST", "/intake/chat", body);
      localStorage.setItem(LS_IN_THREAD, d.thread_id);
      var snap = snapshotFromIntakeResponse(d);
      saveIntakeHandoff(snap);
      renderIntakeOutcomePanel();
      updateOperatorHandoffBanner();
      var dbgW = document.getElementById("in-debug-wrap");
      var dbgP = document.getElementById("in-debug-pre");
      if (d.debug && typeof d.debug === "object") {
        try {
          sessionStorage.setItem(SS_LAST_INTAKE_DEBUG, JSON.stringify(d.debug));
        } catch (e2) {}
        if (!H_CLEAN) {
          dbgW.style.display = "block";
          dbgP.textContent = JSON.stringify(d.debug, null, 2);
        } else {
          dbgW.style.display = "none";
          dbgP.textContent = "";
        }
      } else {
        dbgW.style.display = "none";
        dbgP.textContent = "";
        try {
          sessionStorage.removeItem(SS_LAST_INTAKE_DEBUG);
        } catch (e3) {}
      }
      try {
        sessionStorage.setItem(SS_LAST_INTAKE_TRACE, JSON.stringify(d.trace || []));
      } catch (e4) {}
      bubble(chat, "Assistente", d.reply || "", false);
      traceRender(document.getElementById("trace-in"), d.trace);
      setSt(
        "st-in",
        snap.ticket_id
          ? (H_CLEAN
              ? ("Pratica registrata n. " + snap.ticket_id + (snap.routed_department ? " · reparto " + snap.routed_department : ""))
              : ("API: pratica #" + snap.ticket_id + (snap.routed_department ? " · " + snap.routed_department : "")))
          : (H_CLEAN
              ? "Nessuna nuova pratica in questo messaggio (vedi riepilogo a destra)."
              : "API: nessuna nuova pratica in questo turno (vedi pannello «Esito API»)."),
        snap.ticket_id ? "ok" : ""
      );
      await refreshInbox();
    } catch (err) {
      setSt("st-in", err.message, "err");
    } finally {
      document.getElementById("in-send").disabled = false;
    }
  });

  document.getElementById("in-msg").addEventListener("keydown", function (e) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      document.getElementById("in-send").click();
    }
  });

  document.getElementById("in-new").addEventListener("click", function () {
    localStorage.removeItem(LS_IN_THREAD);
    localStorage.removeItem(LS_LAST_TICKET);
    localStorage.removeItem(LS_LAST_DEPT);
    try {
      sessionStorage.removeItem(SS_INTAKE_HANDOFF);
      sessionStorage.removeItem(SS_LAST_INTAKE_TRACE);
      sessionStorage.removeItem(SS_LAST_INTAKE_DEBUG);
    } catch (e) {}
    document.getElementById("chat-in").innerHTML = "";
    document.getElementById("trace-in").innerHTML = "";
    document.getElementById("inbox-list").innerHTML = "";
    renderIntakeOutcomePanel();
    updateOperatorHandoffBanner();
    setSt("st-in", "Nuova sessione.", "");
  });

  /** ID pratica per posta simulata: stesso snapshot del pannello «Esito API» (evita disallineo con solo localStorage). */
  function inboxTicketIdPreferHandoff() {
    var snap = loadIntakeHandoff();
    if (snap && snap.ticket_id && /^\d+$/.test(String(snap.ticket_id))) {
      return String(snap.ticket_id).trim();
    }
    var ls = localStorage.getItem(LS_LAST_TICKET);
    return ls && /^\d+$/.test(ls) ? ls.trim() : "";
  }

  async function refreshInbox() {
    var tid = inboxTicketIdPreferHandoff();
    var box = document.getElementById("inbox-list");
    if (!tid) {
      box.innerHTML = "<span style='color:var(--muted)'>Nessun ticket_id salvato.</span>";
      return;
    }
    try {
      var d = await apiFetch("GET", "/intake/simulated-mails?ticket_id=" + encodeURIComponent(tid));
      if (!(d.messages || []).length) {
        box.innerHTML = "<span style='color:var(--muted)'>Nessuna mail simulata.</span>";
        return;
      }
      box.innerHTML = (d.messages || []).map(function (m) {
        return "<div style='margin-bottom:0.35rem;border-left:2px solid var(--border);padding-left:0.35rem'><strong>" + esc(m.subject) + "</strong><br/>" + esc(m.body || "") + "</div>";
      }).join("");
    } catch (e) {
      var msg = e && e.message ? e.message : String(e);
      var extra = "";
      if (/non trovato|404/i.test(msg)) {
        extra = H_CLEAN
          ? " Se il riepilogo verde mostra ancora un numero pratica ma qui compare errore, prova «Nuova conversazione» o aggiorna dopo aver verificato il database (es. dopo uno svuotamento ticket)."
          : " Disallineo tipico: snapshot handoff vs ID usato per /intake/simulated-mails, oppure pratica rimossa dal DB (truncate) mentre il browser conserva l’esito. Usa «Nuova conversazione» o allinea LS/handoff.";
      }
      box.innerHTML = "<span style='color:var(--err)'>" + esc(msg) + "</span>" + (extra ? "<br/><span style='color:var(--muted);font-size:0.78rem'>" + esc(extra.trim()) + "</span>" : "");
    }
  }
  document.getElementById("in-inbox-refresh").addEventListener("click", refreshInbox);

  /* --- Operatore --- */
  var __opPraticheList = [];

  function statusLabelIt(st) {
    var m = {
      pending_acceptance: "In coda",
      in_progress: "In lavorazione",
      open: "Aperto",
      resolved: "Risolto"
    };
    return m[st] || String(st || "—");
  }

  function opTicketSelectFill(tickets, preferred) {
    var sel = document.getElementById("op-ticket");
    var keep = preferred != null ? String(preferred) : sel.value;
    sel.innerHTML = "<option value=''>— Seleziona —</option>";
    (tickets || []).forEach(function (t) {
      var o = document.createElement("option");
      o.value = String(t.id);
      o.textContent = String(t.id) + " · " + statusLabelIt(t.status) + " — " + (t.title || "").slice(0, 52)
        + (t.opened_at ? " · " + String(t.opened_at).slice(0, 16) : "");
      sel.appendChild(o);
    });
    if (keep && Array.from(sel.options).some(function (o) { return o.value === keep; })) sel.value = keep;
    else {
      var last = localStorage.getItem(LS_LAST_TICKET);
      if (last && Array.from(sel.options).some(function (o) { return o.value === last; })) sel.value = last;
    }
  }

  async function loadEmployees() {
    var dept = document.getElementById("op-dept").value;
    var sel = document.getElementById("op-emp");
    var prev = sel.value;
    sel.innerHTML = "<option value=''>— Seleziona operatore —</option>";
    if (!_validDept(dept)) {
      var ph = document.createElement("option");
      ph.value = "";
      ph.disabled = true;
      ph.textContent = "Scegli un reparto nel menu oppure clicca una pratica nell’elenco unificato";
      sel.appendChild(ph);
      updateOpMailPanel();
      return;
    }
    try {
      var d = await apiFetch("GET", "/departments/" + encodeURIComponent(dept) + "/employees");
      (d.employees || []).forEach(function (e) {
        var o = document.createElement("option");
        o.value = e.id;
        o.textContent = e.name;
        sel.appendChild(o);
      });
      if (prev && Array.from(sel.options).some(function (o) { return o.value === prev; })) sel.value = prev;
      syncOperatorToAssignee();
    } catch (err) {
      setSt("st-op", err.message, "err");
    }
    updateOpMailPanel();
  }

  function renderGlobalPendingHint(globalPayload, deptLabel, localCount, fetchError, isUnified) {
    var el = document.getElementById("op-pending-global");
    if (!el) return;
    if (fetchError) {
      el.textContent = H_CLEAN
        ? "Impossibile caricare il riepilogo delle richieste in attesa. Riprova tra poco."
        : fetchError;
      return;
    }
    var tickets = (globalPayload && globalPayload.tickets) ? globalPayload.tickets : [];
    var total = (globalPayload && typeof globalPayload.total === "number")
      ? globalPayload.total
      : tickets.length;
    var counts = { vendita: 0, acquisto: 0, manutenzione: 0 };
    tickets.forEach(function (t) {
      var d = t.department;
      if (d && Object.prototype.hasOwnProperty.call(counts, d)) counts[d]++;
    });
    var summary = "vendita " + counts.vendita + ", acquisto " + counts.acquisto + ", manutenzione " + counts.manutenzione;
    if (total === 0) {
      el.innerHTML = H_CLEAN
        ? "<strong>Richieste in attesa in officina:</strong> nessuna al momento. Se nel riepilogo «Richiesta» non compare un numero di pratica, la segnalazione non è stata ancora registrata dal sistema."
        : "<strong>Registry centrale (<code>GET /pratiche/pending</code>):</strong> nessuna pratica in attesa in <em>nessun</em> reparto. " +
          "Se in Richiesta l’«Esito API» non mostra un ID, l’intake non ha eseguito lo strumento di apertura pratica: " +
          "<strong>non</strong> è un errore di passaggio verso pending — la riga non esiste nel DB.";
      return;
    }
    if (isUnified) {
      if (H_CLEAN) {
        el.innerHTML =
          "<strong>In tutta l’officina</strong> ci sono <strong>" + total + "</strong> richieste ancora da prendere in carico (" + summary + "). " +
          "Nell’elenco unificato sotto compaiono <strong>tutte</strong> le pratiche (tutti i reparti). Cliccando una riga si imposta il reparto per operatore e azioni.";
      } else {
        el.innerHTML =
          "<strong>Registry:</strong> " + total + " in coda (" + summary + "). " +
          "<strong>Vista unificata (<code>GET /pratiche</code>):</strong> elenco = tutte le pratiche; " +
          "pratiche ancora <em>In coda</em> in questa lista: <strong>" + localCount + "</strong>.";
      }
      return;
    }
    if (H_CLEAN) {
      el.innerHTML =
        "<strong>In tutta l’officina</strong> ci sono <strong>" + total + "</strong> richieste ancora da prendere in carico (" + summary + "). " +
        "Nel reparto <strong>" + esc(deptLabel) + "</strong> quelle ancora «In coda» sono <strong>" + localCount + "</strong>. " +
        "L’elenco sotto riporta tutte le pratiche di questo reparto.";
      if (localCount === 0 && total > 0) {
        el.innerHTML += " <span style='color:var(--err)'>Qui non ce ne sono: prova «Tutti i reparti» o un altro reparto.</span>";
      }
      return;
    }
    el.innerHTML =
      "<strong>Registry centrale:</strong> " + total + " in coda (" + summary + "). " +
      "Reparto «<strong>" + esc(deptLabel) + "</strong>»: pratiche ancora <em>In coda</em>: <strong>" + localCount + "</strong>. " +
      "L’elenco sotto mostra <strong>tutte</strong> le pratiche del reparto (ogni stato).";
    if (localCount === 0 && total > 0) {
      el.innerHTML += " <span style='color:var(--err)'>Nessuna in coda qui: il totale è in altri reparti — prova vista unificata o altro reparto.</span>";
    }
  }

  function opHighlightRow(praticaId) {
    document.querySelectorAll(".op-pr-row").forEach(function (r) {
      r.classList.toggle("is-sel", !!(praticaId && r.getAttribute("data-id") === String(praticaId)));
    });
  }

  function getSelectedPraticaMeta() {
    var id = document.getElementById("op-ticket").value.trim();
    if (!id) return null;
    var found = null;
    (__opPraticheList || []).forEach(function (p) {
      if (String(p.id) === id) found = p;
    });
    return found;
  }

  function updateOpResolveButton() {
    var btn = document.getElementById("op-resolve");
    var hint = document.getElementById("op-resolve-hint");
    if (!btn) return;
    var meta = getSelectedPraticaMeta();
    var empId = document.getElementById("op-emp").value.trim();
    var ok =
      !!meta &&
      meta.status === "in_progress" &&
      !!empId &&
      empIdsMatch(meta.assigned_to, empId);
    btn.disabled = !ok;
    if (hint) {
      if (ok) {
        hint.textContent = "";
      } else if (!meta) {
        hint.textContent = H_CLEAN
          ? "Per chiudere: seleziona una pratica dall’elenco o dal menu «Pratica selezionata»."
          : "Chiusura: seleziona una pratica (stato «In lavorazione» nel registry).";
      } else if (meta.status !== "in_progress") {
        hint.textContent = H_CLEAN
          ? "Solo le pratiche «In lavorazione» (dopo «Prendi in carico») si possono chiudere. Stato attuale: " + statusLabelIt(meta.status) + "."
          : "Resolve consentito solo con status in_progress (ora: " + esc(meta.status) + ").";
      } else if (!empId) {
        hint.textContent = H_CLEAN
          ? "Scegli l’operatore nel menu: deve essere la persona a cui è assegnata la pratica (dopo il click sulla riga viene impostato automaticamente se possibile)."
          : "Seleziona operatore = assigned_to della pratica (sync automatico dopo caricamento elenco).";
      } else if (!empIdsMatch(meta.assigned_to, empId)) {
        hint.textContent = H_CLEAN
          ? "Operatore selezionato diverso dall’assegnatario: la pratica è di " + (meta.assigned_to_name || "un altro operatore") + ". Scegli il nome corretto nel menu Operatore."
          : "assigned_to ≠ operatore selezionato. Allinea il menu Operatore a: " + esc(meta.assigned_to_name || meta.assigned_to || "?");
      } else {
        hint.textContent = "";
      }
    }
  }

  function updateOpMailPanel() {
    var hint = document.getElementById("op-mail-hint");
    var btn = document.getElementById("op-mail-send");
    var empId = document.getElementById("op-emp").value.trim();
    var meta = getSelectedPraticaMeta();
    if (!meta) {
      hint.textContent = "Seleziona una pratica dall’elenco.";
      btn.disabled = true;
      updateOpResolveButton();
      return;
    }
    if (meta.status === "pending_acceptance") {
      hint.textContent = "Pratica «In coda»: usa «Prendi in carico» (con te come operatore) prima di scrivere al richiedente.";
      btn.disabled = true;
      updateOpResolveButton();
      return;
    }
    if (meta.status !== "in_progress") {
      hint.textContent = "Invio diretto consigliato per pratiche «In lavorazione». Stato attuale: " + statusLabelIt(meta.status) + ".";
      btn.disabled = true;
      updateOpResolveButton();
      return;
    }
    if (!empId) {
      hint.textContent = "Seleziona l’operatore (deve essere l’assegnatario della pratica).";
      btn.disabled = true;
      updateOpResolveButton();
      return;
    }
    if (!empIdsMatch(meta.assigned_to, empId)) {
      hint.innerHTML =
        "Operatore selezionato diversa dall’assegnataria/o: <strong>" +
        esc(meta.assigned_to_name || "altro utente") +
        "</strong> ha la pratica. Cambia operatore o pratica.";
      btn.disabled = true;
      updateOpResolveButton();
      return;
    }
    var em = (meta.customer_email || meta.source_email || "").trim();
    hint.textContent = em
      ? "Destinatario: " + em + "."
      : "Email destinatario ricavata dal ticket di reparto.";
    btn.disabled = false;
    updateOpResolveButton();
  }

  async function loadPraticheElenco() {
    var deptSel = document.getElementById("op-dept").value;
    var isUnified = !_validDept(deptSel);
    var prev = document.getElementById("op-ticket").value;
    var elenco = document.getElementById("op-pratiche-elenco");
    var globalPayload = { tickets: [], total: 0 };
    var globalFetchError = null;
    try {
      globalPayload = await apiFetch("GET", "/pratiche/pending");
    } catch (eg) {
      globalFetchError = "Impossibile leggere /pratiche/pending: " + (eg.message || String(eg));
    }
    try {
      var dept = deptSel;
      if (_validDept(dept)) {
        var lastT = localStorage.getItem(LS_LAST_TICKET);
        if (lastT) {
          try {
            var loc0 = await apiFetch("GET", "/tickets/" + encodeURIComponent(lastT) + "/department");
            if (
              loc0.department &&
              ["vendita", "acquisto", "manutenzione"].indexOf(loc0.department) >= 0 &&
              loc0.department !== dept
            ) {
              document.getElementById("op-dept").value = loc0.department;
              localStorage.setItem(LS_LAST_DEPT, loc0.department);
              await loadEmployees();
              dept = loc0.department;
              isUnified = false;
            }
          } catch (e0) {}
        }
      }
      var d = isUnified
        ? await apiFetch("GET", "/pratiche")
        : await apiFetch("GET", "/departments/" + encodeURIComponent(dept) + "/pratiche");
      var list = d.pratiche || [];
      __opPraticheList = list;
      var pendingHere = list.filter(function (p) {
        return p.status === "pending_acceptance";
      }).length;
      var hintLabel = isUnified ? "tutti i reparti" : dept;
      renderGlobalPendingHint(globalPayload, hintLabel, pendingHere, globalFetchError, isUnified);
      if (!list.length) {
        elenco.innerHTML =
          "<div style='padding:0.65rem;color:var(--muted)'>" +
          (isUnified
            ? (H_CLEAN
                ? "Nessuna pratica nel registry. Quando un richiedente completa l’intake, comparirà qui."
                : "Nessuna riga in <code>GET /pratiche</code>.")
            : (H_CLEAN
                ? "Nessuna pratica in questo reparto. Usa «Tutti i reparti» o prova un altro reparto."
                : "Nessuna pratica in questo reparto. Se il registry globale segnala code, prova vista unificata o altro reparto.")) +
          "</div>";
        opTicketSelectFill([], null);
        opHighlightRow("");
        updateOpMailPanel();
        return 0;
      }
      elenco.innerHTML = list
        .map(function (p) {
          var asn = p.assigned_to_name
            ? esc(p.assigned_to_name)
            : p.assigned_to
              ? "<span style='color:var(--muted)'>(id operatore)</span>"
              : "—";
          var tit = esc((p.title || "").slice(0, 72));
          var rq = esc((p.customer_name || "").slice(0, 40) || "—");
          var dep = esc((p.department || "—").slice(0, 14));
          return (
            "<div class='op-pr-row' role='button' tabindex='0' data-id='" +
            esc(p.id) +
            "' data-dept='" +
            esc(p.department || "") +
            "' data-status='" +
            esc(p.status) +
            "'>" +
            "<span><code>" +
            esc(p.id) +
            "</code></span>" +
            "<span>" +
            esc(statusLabelIt(p.status)) +
            "</span>" +
            "<span>" +
            dep +
            "</span>" +
            "<span>" +
            tit +
            "</span>" +
            "<span>" +
            rq +
            "</span>" +
            "<span>" +
            asn +
            "</span>" +
            "</div>"
          );
        })
        .join("");
      elenco.querySelectorAll(".op-pr-row").forEach(function (row) {
        async function pick() {
          var pid = row.getAttribute("data-id");
          var rowDept = row.getAttribute("data-dept");
          if (!document.getElementById("op-dept").value && _validDept(rowDept)) {
            document.getElementById("op-dept").value = rowDept;
            try {
              localStorage.setItem(LS_LAST_DEPT, rowDept);
            } catch (e1) {}
            await loadEmployees();
          }
          document.getElementById("op-ticket").value = pid;
          opHighlightRow(pid);
          syncOperatorToAssignee();
          updateOpMailPanel();
          await opLoadThread();
        }
        row.addEventListener("click", function () {
          pick().catch(function (e) {
            setSt("st-op", e && e.message ? e.message : String(e), "err");
          });
        });
        row.addEventListener("keydown", function (e) {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            pick().catch(function (err) {
              setSt("st-op", err && err.message ? err.message : String(err), "err");
            });
          }
        });
      });
      opTicketSelectFill(list, prev);
      var sel = document.getElementById("op-ticket");
      if (prev && Array.from(sel.options).some(function (o) { return o.value === prev; })) {
        opHighlightRow(prev);
      } else {
        var last = localStorage.getItem(LS_LAST_TICKET);
        if (last && Array.from(sel.options).some(function (o) { return o.value === last; })) {
          sel.value = last;
          opHighlightRow(last);
        } else opHighlightRow(sel.value);
      }
      syncOperatorToAssignee();
      updateOpMailPanel();
      return list.length;
    } catch (err) {
      elenco.innerHTML = "<div style='padding:0.65rem;color:var(--err)'>" + esc(err.message) + "</div>";
      __opPraticheList = [];
      opTicketSelectFill([], null);
      try {
        var dFail = document.getElementById("op-dept").value;
        renderGlobalPendingHint(
          globalPayload,
          _validDept(dFail) ? dFail : "tutti i reparti",
          0,
          globalFetchError,
          !_validDept(dFail)
        );
      } catch (_) {}
      opHighlightRow("");
      updateOpMailPanel();
      return 0;
    }
  }

  async function opOnShow() {
    updateOperatorHandoffBanner();
    var ld = localStorage.getItem(LS_LAST_DEPT);
    document.getElementById("op-dept").value = ld && _validDept(ld) ? ld : "";
    await loadEmployees();
    await loadPraticheElenco();
    opLoadThread();
  }

  document.getElementById("op-dept").addEventListener("change", async function () {
    await loadEmployees();
    await loadPraticheElenco();
    opLoadThread();
  });
  document.getElementById("op-pending").addEventListener("click", function () {
    loadPraticheElenco();
  });
  document.getElementById("op-ticket").addEventListener("change", function () {
    var sel = this;
    (async function () {
      if (!_validDept(document.getElementById("op-dept").value)) {
        var meta = getSelectedPraticaMeta();
        if (meta && _validDept(meta.department)) {
          document.getElementById("op-dept").value = meta.department;
          try {
            localStorage.setItem(LS_LAST_DEPT, meta.department);
          } catch (e) {}
          await loadEmployees();
        }
      }
      syncOperatorToAssignee();
      opHighlightRow(sel.value);
      updateOpMailPanel();
      await opLoadThread();
    })().catch(function (e) {
      setSt("st-op", e && e.message ? e.message : String(e), "err");
    });
  });
  document.getElementById("op-emp").addEventListener("change", function () {
    updateOpMailPanel();
    opLoadThread();
  });

  document.getElementById("op-accept").addEventListener("click", async function () {
    var eff = operatorEffectiveDept();
    var ticketId = document.getElementById("op-ticket").value.trim();
    var empId = document.getElementById("op-emp").value.trim();
    if (!ticketId || !empId) {
      setSt("st-op", "Seleziona pratica ed operatore.", "err");
      return;
    }
    if (!_validDept(eff)) {
      setSt(
        "st-op",
        "Imposta il reparto dal menu oppure seleziona la pratica dall’elenco unificato (click sulla riga imposta il reparto).",
        "err"
      );
      return;
    }
    var meta = getSelectedPraticaMeta();
    if (!meta || meta.status !== "pending_acceptance") {
      setSt("st-op", "«Prendi in carico» vale solo per pratiche in stato «In coda».", "err");
      return;
    }
    setSt("st-op", "Accettazione…", "load");
    try {
      await apiFetch("POST", "/departments/" + encodeURIComponent(eff) + "/tickets/" + encodeURIComponent(ticketId) + "/accept", { employee_id: empId });
      setSt("st-op", "Presa in carico riuscita. Puoi scrivere al richiedente o usare la chat assistenza.", "ok");
      await loadPraticheElenco();
      opLoadThread();
    } catch (err) {
      setSt("st-op", err.message, "err");
    }
  });

  document.getElementById("op-mail-send").addEventListener("click", async function () {
    var eff = operatorEffectiveDept();
    var praticaId = document.getElementById("op-ticket").value.trim();
    var empId = document.getElementById("op-emp").value.trim();
    var subject = document.getElementById("op-mail-subject").value.trim();
    var bodyM = document.getElementById("op-mail-body").value.trim();
    if (!praticaId || !empId || !subject || !bodyM) {
      setSt("st-op", "Compila oggetto, testo e verifica operatore/pratica.", "err");
      return;
    }
    if (!_validDept(eff)) {
      setSt("st-op", "Reparto non determinato: menu reparto o click su una riga dell’elenco.", "err");
      return;
    }
    setSt("st-op", "Invio mail simulata…", "load");
    document.getElementById("op-mail-send").disabled = true;
    try {
      await apiFetch("POST", "/departments/" + encodeURIComponent(eff) + "/pratiche/" + encodeURIComponent(praticaId) + "/mail-richiedente", {
        employee_id: empId,
        subject: subject,
        body: bodyM
      });
      document.getElementById("op-mail-subject").value = "";
      document.getElementById("op-mail-body").value = "";
      setSt("st-op", "Messaggio registrato: il richiedente lo vede nel tab Richiesta (posta simulata).", "ok");
    } catch (err) {
      setSt("st-op", err.message, "err");
    } finally {
      updateOpMailPanel();
    }
  });

  document.getElementById("op-resolve").addEventListener("click", async function () {
    var eff = operatorEffectiveDept();
    var praticaId = document.getElementById("op-ticket").value.trim();
    var empId = document.getElementById("op-emp").value.trim();
    if (!praticaId || !empId) {
      setSt("st-op", "Seleziona pratica ed operatore (assegnatario).", "err");
      return;
    }
    if (!_validDept(eff)) {
      setSt("st-op", "Reparto non determinato per la chiusura.", "err");
      return;
    }
    var meta = getSelectedPraticaMeta();
    if (!meta || meta.status !== "in_progress" || String(meta.assigned_to || "") !== empId) {
      setSt("st-op", "Chiusura consentita solo all’assegnatario con pratica «In lavorazione».", "err");
      return;
    }
    setSt("st-op", "Chiusura pratica…", "load");
    document.getElementById("op-resolve").disabled = true;
    try {
      await apiFetch("POST", "/departments/" + encodeURIComponent(eff) + "/pratiche/" + encodeURIComponent(praticaId) + "/resolve", {
        employee_id: empId
      });
      setSt("st-op", "Pratica chiusa (risolta).", "ok");
      await loadPraticheElenco();
      await opLoadThread();
    } catch (err) {
      setSt("st-op", err.message, "err");
    } finally {
      updateOpMailPanel();
      updateOpResolveButton();
    }
  });

  async function opLoadThread() {
    var dept = operatorEffectiveDept();
    var ticketId = document.getElementById("op-ticket").value.trim();
    var empId = document.getElementById("op-emp").value.trim();
    var chat = document.getElementById("chat-op");
    var trace = document.getElementById("trace-op");
    trace.innerHTML = "";
    if (!ticketId || !empId) {
      chat.innerHTML = "";
      setSt("st-op", "Scegli pratica (menu) e operatore.", "");
      return;
    }
    if (!_validDept(dept)) {
      chat.innerHTML = "";
      setSt("st-op", "Imposta il reparto (menu o click riga in vista unificata) per usare la chat assistenza.", "");
      return;
    }
    var key = assistStorageKey(dept, ticketId, empId);
    var threadId = localStorage.getItem(key);
    if (!threadId) {
      chat.innerHTML = "";
      setSt("st-op", "Dopo presa in carico (in_progress) invia un messaggio per aprire il thread.", "");
      return;
    }
    try {
      var url = "/assist/thread?department=" + encodeURIComponent(dept)
        + "&ticket_id=" + encodeURIComponent(ticketId)
        + "&employee_id=" + encodeURIComponent(empId)
        + "&thread_id=" + encodeURIComponent(threadId);
      var d = await apiFetch("GET", url);
      chat.innerHTML = "";
      (d.messages || []).forEach(function (m) {
        if (m.role === "user") bubble(chat, "Operatore", m.content, true);
        else if (m.role === "assistant") bubble(chat, "Assistente", m.content, false);
      });
      setSt("st-op", "Cronologia caricata.", "ok");
    } catch (err) {
      chat.innerHTML = "";
      setSt("st-op", err.message, "err");
    }
  }

  document.getElementById("op-send").addEventListener("click", async function () {
    var dept = operatorEffectiveDept();
    var ticketId = document.getElementById("op-ticket").value.trim();
    var empId = document.getElementById("op-emp").value.trim();
    var message = document.getElementById("op-msg").value.trim();
    if (!ticketId || !empId || !message) {
      setSt("st-op", "Pratica, operatore e messaggio obbligatori.", "err");
      return;
    }
    if (!_validDept(dept)) {
      setSt("st-op", "Reparto non determinato: menu o click su una pratica nell’elenco unificato.", "err");
      return;
    }
    var key = assistStorageKey(dept, ticketId, empId);
    var threadId = localStorage.getItem(key);
    var body = { department: dept, ticket_id: ticketId, employee_id: empId, message: message };
    if (threadId) body.thread_id = threadId;

    setSt("st-op", "Invio…", "load");
    document.getElementById("op-send").disabled = true;
    var chat = document.getElementById("chat-op");
    bubble(chat, "Operatore", message, true);
    document.getElementById("op-msg").value = "";

    try {
      var d = await apiFetch("POST", "/assist/chat", body);
      localStorage.setItem(key, d.thread_id);
      bubble(chat, "Assistente", d.reply || "", false);
      traceRender(document.getElementById("trace-op"), d.trace);
      setSt("st-op", "OK", "ok");
    } catch (err) {
      setSt("st-op", err.message, "err");
    } finally {
      document.getElementById("op-send").disabled = false;
    }
  });

  document.getElementById("op-msg").addEventListener("keydown", function (e) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      document.getElementById("op-send").click();
    }
  });

  document.getElementById("op-mail-body").addEventListener("keydown", function (e) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      document.getElementById("op-mail-send").click();
    }
  });

  document.getElementById("op-new-thread").addEventListener("click", function () {
    var dept = operatorEffectiveDept();
    var ticketId = document.getElementById("op-ticket").value.trim();
    var empId = document.getElementById("op-emp").value.trim();
    if (ticketId && empId && _validDept(dept)) localStorage.removeItem(assistStorageKey(dept, ticketId, empId));
    document.getElementById("chat-op").innerHTML = "";
    document.getElementById("trace-op").innerHTML = "";
    setSt("st-op", "Thread locale azzerato per questa tripla.", "");
  });

  /** Ricarica UI da server e storage: usato all’avvio e dopo reload (anche bfcache). */
  async function bootstrapUi() {
    loadContact();
    restoreHandoffSnapshotIfNeeded();
    try {
      await reconcileHandoffWithServer();
    } catch (e) {}
    renderIntakeOutcomePanel();
    updateOperatorHandoffBanner();
    try {
      await loadInThread();
    } catch (e) {}
    try {
      var trRaw = sessionStorage.getItem(SS_LAST_INTAKE_TRACE);
      if (trRaw) {
        var tr = JSON.parse(trRaw);
        if (Array.isArray(tr) && tr.length) traceRender(document.getElementById("trace-in"), tr);
      }
    } catch (e) {}
    try {
      var dbgRaw = sessionStorage.getItem(SS_LAST_INTAKE_DEBUG);
      var dbgW = document.getElementById("in-debug-wrap");
      var dbgP = document.getElementById("in-debug-pre");
      if (dbgRaw && !H_CLEAN) {
        var dbgObj = JSON.parse(dbgRaw);
        if (dbgObj && typeof dbgObj === "object") {
          dbgW.style.display = "block";
          dbgP.textContent = JSON.stringify(dbgObj, null, 2);
        }
      }
    } catch (e) {}
    if (localStorage.getItem(LS_LAST_TICKET)) {
      try {
        await refreshInbox();
      } catch (e) {}
    }
    var savedDept = localStorage.getItem(LS_LAST_DEPT);
    document.getElementById("op-dept").value = _validDept(savedDept) ? savedDept : "";
    try {
      await loadEmployees();
      await loadPraticheElenco();
    } catch (e) {}
  }

  bootstrapUi().catch(function (e) {
    console.error(e);
    setSt("st-in", "Errore aggiornamento dopo reload: " + (e && e.message ? e.message : String(e)), "err");
  });

  window.addEventListener("pageshow", function (ev) {
    if (ev.persisted) {
      bootstrapUi().catch(function (e) {
        console.error(e);
      });
    }
  });
})();

