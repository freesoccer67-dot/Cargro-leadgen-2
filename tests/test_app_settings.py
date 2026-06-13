import pandas as pd

from app import build_url_dataframe, settings_for_provider, settings_with_secret_values
from leadgen.config import Settings


def test_settings_for_provider_uses_serpapi_key_from_ui():
    settings = Settings(search_provider="manual", serpapi_api_key="")

    updated = settings_for_provider(settings, "serpapi", "secret-key")

    assert updated.search_provider == "serpapi"
    assert updated.serpapi_api_key == "secret-key"


def test_settings_with_secret_values_defaults_to_serpapi_when_key_exists():
    settings = Settings(search_provider="manual", serpapi_api_key="")

    updated = settings_with_secret_values(settings, {"SERPAPI_API_KEY": "secret-key"})

    assert updated.search_provider == "serpapi"
    assert updated.serpapi_api_key == "secret-key"


def test_settings_with_secret_values_uses_configured_provider():
    settings = Settings(search_provider="manual", serpapi_api_key="")

    updated = settings_with_secret_values(
        settings,
        {"SEARCH_PROVIDER": "bing", "BING_SEARCH_API_KEY": "bing-key"},
    )

    assert updated.search_provider == "bing"
    assert updated.bing_search_api_key == "bing-key"


def test_build_url_dataframe_does_not_search_on_page_load(monkeypatch):
    def fail_discover(*args, **kwargs):
        raise AssertionError("search API should not be called")

    monkeypatch.setattr("app.discover_urls", fail_discover)
    keywords_df = pd.DataFrame([{"keyword": "tuinmeubelen webshop", "category": "garden"}])
    manual_df = pd.DataFrame([{"url": "https://example.nl", "category": "manual"}])

    urls = build_url_dataframe(keywords_df, manual_df, Settings(search_provider="serpapi"), 5)

    assert urls["url"].tolist() == ["https://example.nl/"]
