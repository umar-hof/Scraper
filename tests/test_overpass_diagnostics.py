import pytest
import respx
from httpx import Response

from app.discovery import OverpassDiscovery, OverpassRequestError


@pytest.mark.asyncio
@respx.mock
async def test_http_406_report_preserves_server_diagnostics():
    respx.get("https://overpass.example/api/status").mock(return_value=Response(200, text="ok"))
    respx.post("https://overpass.example/api/interpreter").mock(
        return_value=Response(406, text="Not Acceptable: endpoint policy")
    )
    adapter = OverpassDiscovery("https://overpass.example/api/interpreter", "test-agent", timeout=10, max_retries=0, min_interval_seconds=0)
    async with adapter:
        with pytest.raises(OverpassRequestError) as caught:
            await adapter.search("Phoenix", (33.2, -112.3, 33.8, -111.8), "candle")
    report = caught.value.report
    assert report.status_code == 406
    assert report.method == "POST"
    assert "endpoint policy" in (report.response_excerpt or "")
    assert "HTTP 406" in (report.error or "")
