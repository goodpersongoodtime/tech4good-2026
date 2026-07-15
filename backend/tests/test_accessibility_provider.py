from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from app.domain import ProviderLeg, ProviderRoute
from app.models import (
    Coordinate,
    DataConfidence,
    DataSource,
    FacilityStatus,
    LegMode,
    PlaceInput,
    RouteMode,
)
from app.providers.accessibility import HybridAccessibilityProvider
from app.providers.seoul import SeoulElevator


class PartialElevatorClient:
    async def get_elevator(self, station_name: str):
        if station_name == "탑승역":
            return SeoulElevator(
                status=FacilityStatus.AVAILABLE,
                location_description="1번 출구",
                confidence=DataConfidence.VERIFIED,
            )
        return None


@pytest.mark.asyncio
async def test_subway_requires_elevator_data_for_both_boarding_and_alighting_station() -> None:
    start = PlaceInput(
        name="탑승역",
        coordinate=Coordinate(latitude=37.5, longitude=127.0),
    )
    end = PlaceInput(
        name="하차역",
        coordinate=Coordinate(latitude=37.51, longitude=127.01),
    )
    route = ProviderRoute(
        provider_route_id="subway-route",
        mode=RouteMode.TRANSIT,
        title="지하철 경로",
        standard_duration_sec=600,
        total_distance_m=3000,
        walk_distance_m=0,
        transfer_count=0,
        fare_krw=1500,
        legs=[
            ProviderLeg(
                provider_leg_id="subway-leg",
                mode=LegMode.SUBWAY,
                start=start,
                end=end,
                distance_m=3000,
                duration_sec=600,
                geometry=[[127.0, 37.5], [127.01, 37.51]],
                line_id="SUBWAY_LINE_1",
                line_name="1호선",
                departure_at=datetime(2026, 7, 15, 14, 0, tzinfo=ZoneInfo("Asia/Seoul")),
                arrival_at=datetime(2026, 7, 15, 14, 10, tzinfo=ZoneInfo("Asia/Seoul")),
            )
        ],
    )

    context = await HybridAccessibilityProvider(PartialElevatorClient()).get_context([route])
    subway = context.subway["subway-leg"]

    assert subway.elevator_status == FacilityStatus.UNKNOWN
    assert subway.confidence == DataConfidence.UNKNOWN
    assert subway.source == DataSource.SEOUL_OPEN_DATA
