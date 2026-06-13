import requests

from leadgen.search_api import _safe_request_error


def test_safe_request_error_redacts_api_key_from_url():
    request = requests.Request(
        "GET",
        "https://serpapi.com/search.json",
        params={"q": "test", "api_key": "secret-key"},
    ).prepare()
    error = requests.RequestException(f"Failed for {request.url}")
    error.request = request

    message = _safe_request_error(error)

    assert "secret-key" not in message
    assert "api_key=%2A%2A%2A" in message
