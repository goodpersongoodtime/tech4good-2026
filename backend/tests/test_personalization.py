from datetime import datetime
from zoneinfo import ZoneInfo

from app.domain import (
    AccessibilityContext,
    BusAccessibility,
    ProviderLeg,
    ProviderRoute,
    StationAccessibility,
    WalkAccessibility,
)
from app.main import demo_profile
from app.models import Coordinate, DataConfidence, LegMode, LowFloorStatus, PlaceInput, RouteMode
from app.personalization import BaselinePersonalizationEngine

SEOUL = ZoneInfo("Asia/Seoul")
NOW = datetime(2026, 7, 15, 14, 0, tzinfo=SEOUL)


def place(name: str, latitude: float, longitude: float) -> PlaceInput:
    return PlaceInput(name=name, coordinate=Coordinate(latitude=latitude, longitude=longitude))


def line(start: PlaceInput, end: PlaceInput) -> list[list[float]]:
    return [
        [start.coordinate.longitude, start.coordinate.latitude],
        [end.coordinate.longitude, end.coordinate.latitude],
    ]


def test_recalculates_walk_time_from_profile_speed() -> None:
    origin = place("서울역", 37.5547, 126.9707)
    destination = place("시청", 37.5663, 126.9779)
    candidate = ProviderRoute(
        provider_route_id="walk-1",
        mode=RouteMode.WALK,
        title="도보 경로",
        standard_duration_sec=900,
        total_distance_m=800,
        walk_distance_m=800,
        transfer_count=0,
        fare_krw=0,
        legs=[
            ProviderLeg(
                provider_leg_id="walk-leg-1",
                mode=LegMode.WALK,
                start=origin,
                end=destination,
                distance_m=800,
                duration_sec=900,
                geometry=line(origin, destination),
            )
        ],
    )
    context = AccessibilityContext(
        walk={
            "walk-leg-1": WalkAccessibility(
                has_stairs=False,
                max_slope_percent=4.0,
                confidence=DataConfidence.ESTIMATED,
            )
        }
    )

    [route] = BaselinePersonalizationEngine().personalize_routes(
        [candidate], demo_profile(), context, NOW
    )

    assert route.legs[0].personalized_duration_sec == 1000
    assert route.summary.personalized_duration_sec == 1000
    assert route.summary.arrival_at == datetime(2026, 7, 15, 14, 16, 40, tzinfo=SEOUL)
    assert route.accessibility_status == "ACCESSIBLE"


def test_marks_explicitly_inaccessible_transit_route_unavailable() -> None:
    origin = place("정류장 A", 37.5, 127.0)
    destination = place("정류장 B", 37.51, 127.01)
    candidate = ProviderRoute(
        provider_route_id="bus-1",
        mode=RouteMode.TRANSIT,
        title="일반버스 경로",
        standard_duration_sec=600,
        total_distance_m=3000,
        walk_distance_m=0,
        transfer_count=0,
        fare_krw=1500,
        legs=[
            ProviderLeg(
                provider_leg_id="bus-leg-1",
                mode=LegMode.BUS,
                start=origin,
                end=destination,
                distance_m=3000,
                duration_sec=600,
                geometry=line(origin, destination),
                route_id="100",
                route_name="100번",
                departure_at=NOW,
                arrival_at=datetime(2026, 7, 15, 14, 10, tzinfo=SEOUL),
            )
        ],
    )
    context = AccessibilityContext(
        bus={
            "bus-leg-1": BusAccessibility(
                low_floor_status=LowFloorStatus.NOT_LOW_FLOOR,
                confidence=DataConfidence.VERIFIED,
            )
        }
    )

    [route] = BaselinePersonalizationEngine().personalize_routes(
        [candidate], demo_profile(), context, NOW
    )

    assert route.accessibility_status == "UNAVAILABLE"
    assert route.unavailable_reasons[0].code == "LOW_FLOOR_BUS_REQUIRED"


def test_personalized_walk_time_never_becomes_shorter_than_provider_time() -> None:
    origin = place("출발", 37.5, 127.0)
    destination = place("도착", 37.51, 127.01)
    candidate = ProviderRoute(
        provider_route_id="slow-provider-walk",
        mode=RouteMode.WALK,
        title="혼잡한 보행 경로",
        standard_duration_sec=1200,
        total_distance_m=800,
        walk_distance_m=800,
        transfer_count=0,
        fare_krw=0,
        legs=[
            ProviderLeg(
                provider_leg_id="slow-walk-leg",
                mode=LegMode.WALK,
                start=origin,
                end=destination,
                distance_m=800,
                duration_sec=1200,
                geometry=line(origin, destination),
            )
        ],
    )
    context = AccessibilityContext(
        walk={
            "slow-walk-leg": WalkAccessibility(
                has_stairs=False,
                max_slope_percent=2,
                confidence=DataConfidence.VERIFIED,
            )
        }
    )

    [route] = BaselinePersonalizationEngine().personalize_routes(
        [candidate], demo_profile(), context, NOW
    )

    assert route.legs[0].personalized_duration_sec == 1200
    assert route.summary.personalized_duration_sec == 1200


def test_unknown_elevator_data_is_caution_not_false_unavailable() -> None:
    origin = place("서울역", 37.5547, 126.9707)
    destination = place("시청역", 37.5657, 126.9770)
    candidate = ProviderRoute(
        provider_route_id="subway-1",
        mode=RouteMode.TRANSIT,
        title="1호선",
        standard_duration_sec=120,
        total_distance_m=1000,
        walk_distance_m=0,
        transfer_count=0,
        fare_krw=1500,
        legs=[
            ProviderLeg(
                provider_leg_id="subway-leg-1",
                mode=LegMode.SUBWAY,
                start=origin,
                end=destination,
                distance_m=1000,
                duration_sec=120,
                geometry=line(origin, destination),
                line_id="SUBWAY_LINE_1",
                line_name="1호선",
                departure_at=NOW,
                arrival_at=datetime(2026, 7, 15, 14, 2, tzinfo=SEOUL),
            )
        ],
    )
    context = AccessibilityContext(
        subway={
            "subway-leg-1": StationAccessibility(
                elevator_status=None,
                confidence=DataConfidence.UNKNOWN,
            )
        }
    )

    [route] = BaselinePersonalizationEngine().personalize_routes(
        [candidate], demo_profile(), context, NOW
    )

    assert route.accessibility_status == "CAUTION"
    assert route.warnings[0].code == "ELEVATOR_STATUS_UNKNOWN"


def test_sorts_accessible_before_caution_before_unavailable() -> None:
    origin = place("출발", 37.5, 127.0)
    destination = place("도착", 37.51, 127.01)

    def walk_candidate(candidate_id: str) -> ProviderRoute:
        return ProviderRoute(
            provider_route_id=candidate_id,
            mode=RouteMode.WALK,
            title=candidate_id,
            standard_duration_sec=100,
            total_distance_m=80,
            walk_distance_m=80,
            transfer_count=0,
            fare_krw=0,
            legs=[
                ProviderLeg(
                    provider_leg_id=candidate_id,
                    mode=LegMode.WALK,
                    start=origin,
                    end=destination,
                    distance_m=80,
                    duration_sec=100,
                    geometry=line(origin, destination),
                )
            ],
        )

    candidates = [walk_candidate("unknown"), walk_candidate("stairs"), walk_candidate("safe")]
    context = AccessibilityContext(
        walk={
            "unknown": WalkAccessibility(),
            "stairs": WalkAccessibility(has_stairs=True, confidence=DataConfidence.VERIFIED),
            "safe": WalkAccessibility(
                has_stairs=False,
                max_slope_percent=2.0,
                confidence=DataConfidence.VERIFIED,
            ),
        }
    )

    routes = BaselinePersonalizationEngine().personalize_routes(
        candidates, demo_profile(), context, NOW
    )

    assert [route.accessibility_status for route in routes] == [
        "ACCESSIBLE",
        "CAUTION",
        "UNAVAILABLE",
    ]
    assert [route.rank for route in routes] == [1, 2, 3]
