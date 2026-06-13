from leadgen.extractor import extract_lead


def test_extract_lead_prefers_generic_email_and_signals():
    pages = [
        {
            "url": "https://example.nl",
            "title": "Voorbeeld Tuinmeubelen - Webshop",
            "html": "<html><h1>Voorbeeld Tuinmeubelen</h1></html>",
            "text": (
                "Voorbeeld Tuinmeubelen webshop met loungeset en tuinset. "
                "Wij leveren grote producten op afspraak en halen retouren op. "
                "Contact: jan.jansen@example.nl of info@example.nl. Bel 020 123 4567."
            ),
        },
        {
            "url": "https://example.nl/bezorging",
            "title": "Bezorging",
            "html": "",
            "text": "Bezorging met eigen transport en geplande levering in Nederland.",
        },
    ]

    lead = extract_lead("https://example.nl", pages)

    assert lead["company_name"] == "Voorbeeld Tuinmeubelen"
    assert lead["generic_email"] == "info@example.nl"
    assert lead["country"] == "Netherlands"
    assert lead["webshop_signal"] is True
    assert lead["appointment_delivery_signal"] is True
    assert lead["own_delivery_signal"] is True
    assert "loungeset" in lead["products_detected"]
    assert lead["evidence_snippets"]
