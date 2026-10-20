from unittest.mock import Mock
import pytest
from fba_trends.sp_api import SPAPIClient, SPAPIError, configured


def test_requires_credentials():
    with pytest.raises(SPAPIError):
        SPAPIClient(client_id="", client_secret="", refresh_token="")


def test_configured():
    assert not configured({})
    assert configured({"SP_API_LWA_CLIENT_ID":"a","SP_API_LWA_CLIENT_SECRET":"b","SP_API_REFRESH_TOKEN":"c"})


def test_catalog_search_uses_lwa_token_and_marketplace():
    session = Mock()
    session.post.return_value.json.return_value = {"access_token":"test-access-token", "expires_in":3600}
    session.get.return_value.json.return_value = {"items":[{"asin":"B000000000"}]}
    client = SPAPIClient(client_id="id", client_secret="secret", refresh_token="refresh", session=session)
    assert client.search_catalog("dog bowl")["items"][0]["asin"] == "B000000000"
    assert client.search_catalog("dog bowl")["items"]
    assert session.post.call_count == 1
    kwargs = session.get.call_args.kwargs
    assert kwargs["headers"]["x-amz-access-token"] == "test-access-token"
    assert kwargs["params"]["marketplaceIds"] == "ATVPDKIKX0DER"


def test_invalid_term_prevents_network():
    client = SPAPIClient(client_id="id",client_secret="secret",refresh_token="refresh",session=Mock())
    with pytest.raises(ValueError):
        client.search_catalog("")
