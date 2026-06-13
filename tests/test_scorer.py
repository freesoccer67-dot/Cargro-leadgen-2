from leadgen.scorer import classify_opportunities, priority_from_score, score_lead


def test_high_fit_lead_scores_high():
    lead = {
        "category": "garden furniture",
        "country": "Netherlands",
        "generic_email": "info@example.nl",
        "bulky_product_signals": ["loungeset", "grote producten"],
        "delivery_signals": ["bezorging"],
        "return_signals": ["retour"],
        "appointment_delivery_signal": True,
        "showroom_signal": True,
        "own_delivery_signal": True,
        "webshop_signal": True,
        "small_parcel_signal": False,
    }

    score = score_lead(lead)

    assert score >= 80
    assert priority_from_score(score) == "High priority"
    opportunities = classify_opportunities(lead, score)
    assert "Last-mile bulky delivery" in opportunities
    assert "Return pickup service" in opportunities


def test_low_fit_small_parcel_lead_is_archived():
    lead = {
        "category": "Uncategorized",
        "country": "",
        "generic_email": "",
        "bulky_product_signals": [],
        "delivery_signals": [],
        "return_signals": [],
        "appointment_delivery_signal": False,
        "showroom_signal": False,
        "own_delivery_signal": False,
        "webshop_signal": False,
        "small_parcel_signal": True,
    }

    score = score_lead(lead)

    assert score < 40
    assert classify_opportunities(lead, score) == "Not relevant"
