from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from app.main import demo_profile
from app.models import Coordinate, PlaceInput, RouteMode, RouteSearchRequest
from app.personalization import BaselinePersonalizationEngine
from app.providers.accessibility import HybridAccessibilityProvider
from app.providers.mock import MockRouteProvider
from app.services import RouteService, StoredRoute
from app.storage import MemoryTTLStore

NOW = datetime(2026, 7, 15, 14, 0, tzinfo=ZoneInfo("Asia/Seoul"))


class CountingProvider:
    def __init__(self) -> None:
        self.delegate = MockRouteProvider()
        self.calls = 0

    async def search(self, request: RouteSearchRequest):
        self.calls += 1
        return await self.delegate.search(request)


class FixedAccessibilityProvider(HybridAccessibilityProvider):
    async def get_context(self, routes):
        return await super().get_context(routes)


@pytest.mark.asyncio
async def test_identical_search_and_profile_reuse_ten_minute_result() -> None:
    provider = CountingProvider()
    service = RouteService(
        provider=provider,
        accessibility=FixedAccessibilityProvider(),
        engine=BaselinePersonalizationEngine(),
        store=MemoryTTLStore[StoredRoute](clock=lambda: NOW),
        clock=lambda: NOW,
        ttl_sec=600,
    )
    request = RouteSearchRequest(
        origin=PlaceInput(
            name="서울역",
            coordinate=Coordinate(latitude=37.5547, longitude=126.9707),
        ),
        destination=PlaceInput(
            name="잠실역",
            coordinate=Coordinate(latitude=37.5133, longitude=127.1001),
        ),
        mode=RouteMode.WALK,
        departure_at=NOW,
    )

    first = await service.search(request, demo_profile())
    second = await service.search(request, demo_profile())

    assert provider.calls == 1
    assert second.search_id == first.search_id
    assert second.routes[0].route_id == first.routes[0].route_id
