from app.discovery.overpass import OverpassDiscovery

def test_normalization():
    items = [{"type": "node", "id": 1, "tags": {"name": "Arizona Candle Co", "shop": "candles", "contact:phone": "602-555-0100"}}]
    result = OverpassDiscovery("https://example.test", "test")._normalize(items, "Phoenix")
    assert result[0].name == "Arizona Candle Co"
    assert result[0].phone == "602-555-0100"

def test_query_is_bounded_and_out_syntax_is_valid(monkeypatch):
    adapter = OverpassDiscovery("https://example.test/api/interpreter", "test", min_interval_seconds=0)
    captured = {}

    class Response:
        status_code = 200
        headers = {}
        def json(self): return {"elements": []}

    class Client:
        async def post(self, endpoint, data):
            captured.update(data=data)
            return Response()
        async def get(self, endpoint): return Response()

    async def healthy(): return True
    adapter._client = Client()
    monkeypatch.setattr(adapter, "health_check", healthy)
    import asyncio
    asyncio.run(adapter.search("Phoenix", (33.2, -112.3, 33.8, -111.8), "candle", limit=10))
    query = captured["data"]["data"]
    assert "(33.2,-112.3,33.8,-111.8)" in query
    assert "out center tags;" in query
    assert "area[" not in query

