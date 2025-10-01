import pytest
import respx

from src.integrations.inspect import InspectClient


@pytest.mark.asyncio
async def test_inspect_client_parses_payload():
    client = InspectClient()
    with respx.mock(base_url="http://inspect:5000") as mock:
        mock.get("/", params__url="steam://inspect/123").respond(
            200,
            json={
                "float_value": 0.12,
                "paint_seed": 700,
                "paint_index": 3,
                "stickers": [{"name": "Crown (Foil)"}],
                "wear_name": "Field-Tested",
            },
        )
        result = await client.inspect("steam://inspect/123")
    await client.close()
    assert result is not None
    assert result.paint_seed == 700

