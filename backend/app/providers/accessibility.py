from app.domain import (
    AccessibilityContext,
    BusAccessibility,
    ProviderRoute,
    StationAccessibility,
    WalkAccessibility,
)
from app.errors import ApiError
from app.models import (
    DataConfidence,
    DataSource,
    FacilityStatus,
    LegMode,
    LowFloorStatus,
)
from app.providers.seoul import SeoulDataClient


class HybridAccessibilityProvider:
    """Fixture baseline enriched with Seoul elevator data when configured."""

    def __init__(self, seoul: SeoulDataClient | None = None) -> None:
        self.seoul = seoul

    async def get_context(self, routes: list[ProviderRoute]) -> AccessibilityContext:
        walk = {}
        bus = {}
        subway = {}
        for route in routes:
            for leg in route.legs:
                if leg.mode == LegMode.WALK:
                    walk[leg.provider_leg_id] = WalkAccessibility(
                        has_stairs=False,
                        max_slope_percent=4.0,
                        confidence=DataConfidence.ESTIMATED,
                        source=DataSource.SYNTHETIC_FIXTURE,
                    )
                elif leg.mode == LegMode.BUS:
                    bus[leg.provider_leg_id] = BusAccessibility(
                        low_floor_status=LowFloorStatus.CONFIRMED,
                        confidence=DataConfidence.ESTIMATED,
                        source=DataSource.SYNTHETIC_FIXTURE,
                    )
                elif leg.mode == LegMode.SUBWAY:
                    subway[leg.provider_leg_id] = await self._subway_accessibility(
                        leg.start.name, leg.end.name
                    )
        return AccessibilityContext(walk=walk, bus=bus, subway=subway)

    async def _subway_accessibility(
        self, boarding_station: str, alighting_station: str
    ) -> StationAccessibility:
        if self.seoul is None:
            return StationAccessibility(
                elevator_status=FacilityStatus.AVAILABLE,
                confidence=DataConfidence.ESTIMATED,
                location_description="해커톤 합성 fixture",
                source=DataSource.SYNTHETIC_FIXTURE,
            )
        try:
            boarding = await self.seoul.get_elevator(boarding_station)
            alighting = await self.seoul.get_elevator(alighting_station)
        except ApiError:
            boarding = None
            alighting = None
        if boarding is None or alighting is None:
            return StationAccessibility(
                elevator_status=FacilityStatus.UNKNOWN,
                confidence=DataConfidence.UNKNOWN,
                source=DataSource.SEOUL_OPEN_DATA,
            )
        statuses = {boarding.status, alighting.status}
        status = (
            FacilityStatus.UNAVAILABLE
            if FacilityStatus.UNAVAILABLE in statuses
            else FacilityStatus.AVAILABLE
        )
        descriptions = [
            f"{station}: {facility.location_description}"
            for station, facility in [
                (boarding_station, boarding),
                (alighting_station, alighting),
            ]
            if facility.location_description
        ]
        return StationAccessibility(
            elevator_status=status,
            confidence=(
                DataConfidence.VERIFIED
                if boarding.confidence == alighting.confidence == DataConfidence.VERIFIED
                else DataConfidence.ESTIMATED
            ),
            location_description=" / ".join(descriptions) or None,
            source=DataSource.SEOUL_OPEN_DATA,
        )
