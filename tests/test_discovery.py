import pandas as pd

from leadgen.discovery import (
    build_candidate_row,
    candidates_dataframe,
    import_candidate_urls,
    normalize_candidate_url,
    should_exclude,
)
from leadgen.search_api import SearchResult


def test_normalize_candidate_url_removes_tracking_and_roots_product_pages():
    url = normalize_candidate_url(
        "https://Example.nl/product/loungeset-123?utm_source=google&color=green#g"
    )

    assert url == "https://example.nl/?color=green"


def test_excludes_social_and_pdf_results():
    assert should_exclude("https://linkedin.com/company/example", "Example", "")
    assert should_exclude("https://example.nl/catalogus.pdf", "Catalogus", "")


def test_build_candidate_row_scores_company_result():
    result = SearchResult(
        url="https://tuinvoorbeeld.nl/collections/loungesets?utm_campaign=x",
        title="Tuinvoorbeeld tuinmeubelen webshop",
        snippet="Loungeset bezorgen in Nederland. Contact voor levering en retour.",
        keyword="tuinmeubelen webshop bezorgen Nederland",
        provider="brave",
        rank=1,
    )
    keyword_row = pd.Series(
        {
            "keyword": "tuinmeubelen webshop bezorgen Nederland",
            "category": "garden furniture",
            "country": "Netherlands",
            "language": "nl",
        }
    )

    row = build_candidate_row(result, keyword_row)

    assert row is not None
    assert row["url"] == "https://tuinvoorbeeld.nl/"
    assert row["confidence_score"] >= 80
    assert "keyword appears in title" in row["discovery_reason"]


def test_candidates_keep_best_duplicate_domain():
    rows = [
        {"url": "https://example.nl/", "domain": "example.nl", "confidence_score": 40, "search_rank": 1},
        {"url": "https://example.nl/", "domain": "example.nl", "confidence_score": 80, "search_rank": 2},
    ]

    df = candidates_dataframe(rows)

    assert len(df) == 1
    assert int(df.iloc[0]["confidence_score"]) == 80


def test_import_candidate_urls_accepts_manual_csv_shape():
    df = pd.DataFrame(
        [{"url": "https://example.nl", "category": "webshops", "source": "WebwinkelKeur"}]
    )

    candidates = import_candidate_urls(df)

    assert candidates.iloc[0]["source_provider"] == "WebwinkelKeur"
    assert candidates.iloc[0]["status"] == "New"
