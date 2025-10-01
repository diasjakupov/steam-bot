import pytest
import respx

from src.integrations.inspect import InspectClient


@pytest.mark.asyncio
async def test_inspect_client_parses_payload():
    client = InspectClient()
    with respx.mock(base_url="http://float-api:5000") as mock:
        encoded = "steam%3A%2F%2Finspect%2F123"
        mock.get(f"/?url={encoded}").respond(
            200,
            json={
                "iteminfo": {
                    "floatvalue": 0.12,
                    "paintseed": 700,
                    "paintindex": 3,
                    "stickers": [{"name": "Crown (Foil)"}],
                    "wear_name": "Field-Tested",
                    "full_item_name": "AK-47 | Redline",
                }
            },
        )
        result = await client.inspect("steam://inspect/123")
    await client.close()
    assert result is not None
    assert result.paint_seed == 700
    assert result.custom_name == "AK-47 | Redline"


@pytest.mark.asyncio
async def test_inspect_client_handles_invalid_url():
    client = InspectClient()
    result = await client.inspect("http://example.com")
    await client.close()
    assert result is None
