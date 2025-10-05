import pytest

from src.integrations.inspect import InspectClient


# Note: These tests are disabled because they would require either:
# 1. Mocking Playwright page interactions (complex)
# 2. Actually hitting the CSFloat website (not suitable for CI)
#
# For now, manual testing is recommended for the inspect integration.
# To manually test, run a script that calls InspectClient().inspect(valid_steam_url)

@pytest.mark.skip(reason="InspectClient now uses Playwright to scrape CSFloat website - needs manual testing")
@pytest.mark.asyncio
async def test_inspect_client_manual():
    """
    Manual test: Uncomment and run with a valid inspect URL to test CSFloat integration.

    Example:
    client = InspectClient()
    result = await client.inspect("steam://rungame/730/76561202255233023/+csgo_econ_action_preview%20S76561198084749846A28756825255D7935801027122068185")
    await client.close()
    assert result is not None
    assert result.float_value is not None
    """
    pass
