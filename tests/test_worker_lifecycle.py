import pytest

from app.workers import Worker


class _DiscoveryContext:
    def __init__(self):
        self.entered = False
        self.exited = False

    async def __aenter__(self):
        self.entered = True
        return self

    async def __aexit__(self, *_):
        self.exited = True


@pytest.mark.asyncio
async def test_worker_opens_and_closes_overpass_client(monkeypatch):
    class Settings:
        worker_mode = "scheduled"

    discovery = _DiscoveryContext()
    worker = Worker.__new__(Worker)
    worker.settings = Settings()
    worker.discovery = discovery

    called = False

    async def run_once(dry_run=False):
        nonlocal called
        called = True

    worker.run_once = run_once
    await worker.run()

    assert called
    assert discovery.entered
    assert discovery.exited
