from app import settings_for_provider
from leadgen.config import Settings


def test_settings_for_provider_uses_serpapi_key_from_ui():
    settings = Settings(search_provider="manual", serpapi_api_key="")

    updated = settings_for_provider(settings, "serpapi", "secret-key")

    assert updated.search_provider == "serpapi"
    assert updated.serpapi_api_key == "secret-key"
