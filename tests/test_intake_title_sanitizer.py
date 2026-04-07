from app.tools.intake_tools import format_intake_title, sanitize_intake_title


def test_sanitize_intake_title_removes_contact_block_artifacts():
    title = "[Dati contatto richiedente:"
    summary = (
        "[Dati contatto richiedente:\n"
        "nome=Mario\n"
        "cognome=Rossi\n"
        "email=mario@example.com]\n\n"
        "Rumore freni su Panda 2020, controllo urgente."
    )
    assert sanitize_intake_title(title, summary) == "Rumore freni su Panda 2020, controllo urgente."


def test_sanitize_intake_title_keeps_clean_title():
    title = "Preventivo tagliando Ducato 2021"
    summary = "Richiesta tagliando completo con controllo freni."
    assert sanitize_intake_title(title, summary) == "Richiesta tagliando completo con controllo freni"


def test_sanitize_intake_title_uses_full_summary_not_first_message():
    title = "Tagliando"
    summary = (
        "Primo contatto cliente.\n"
        "Veicolo Fiat Ducato 2019, targa AB123CD, 118000 km.\n"
        "Richiede tagliando completo e verifica rumorosita freni anteriori."
    )
    out = sanitize_intake_title(title, summary)
    assert "tagliando completo" in out.lower()
    assert "freni" in out.lower()


def test_format_intake_title_prefix_by_department():
    summary = "Tagliando completo e verifica freni su Ducato 2019."
    assert format_intake_title("manutenzione", "Tagliando", summary).startswith("[Officina] ")
    assert format_intake_title("acquisto", "Ordine", "Ordine urgente filtri").startswith("[Acquisto] ")
    assert format_intake_title("vendita", "Preventivo", "Preventivo rinnovo flotta").startswith("[Vendita] ")
