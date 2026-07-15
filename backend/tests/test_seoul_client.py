import httpx
import pytest
import respx

from app.models import FacilityStatus
from app.providers.seoul import SeoulDataClient


@pytest.mark.asyncio
@respx.mock
async def test_elevator_presence_is_normalized_as_available() -> None:
    upstream = respx.get(url__regex=r"http://openapi\.seoul\.go\.kr:8088/.*").mock(
        return_value=httpx.Response(
            200,
            json={
                "getFcElvtr": {
                    "row": [
                        {
                            "stnNm": "서울역",
                            "lineNm": "1호선",
                            "dtlLoc": "1번 출구 방면",
                        },
                        {
                            "stnNm": "시청역",
                            "lineNm": "1호선",
                            "dtlLoc": "환승 통로 방면",
                        },
                    ]
                }
            },
        )
    )
    async with httpx.AsyncClient() as client:
        seoul = SeoulDataClient("seoul-key", client)
        facility = await seoul.get_elevator("서울역")
        second = await seoul.get_elevator("시청역")

    assert facility is not None
    assert facility.status == FacilityStatus.AVAILABLE
    assert facility.location_description == "1번 출구 방면"
    assert second is not None
    assert upstream.call_count == 1


@pytest.mark.asyncio
@respx.mock
async def test_realtime_subway_returns_soonest_nonnegative_arrival() -> None:
    respx.get(url__regex=r"http://swopenapi\.seoul\.go\.kr/.*").mock(
        return_value=httpx.Response(
            200,
            json={
                "realtimeArrivalList": [
                    {"statnNm": "시청", "barvlDt": "180"},
                    {"statnNm": "시청", "barvlDt": "45"},
                ]
            },
        )
    )
    async with httpx.AsyncClient() as client:
        seconds = await SeoulDataClient("seoul-key", client).get_next_arrival_sec("시청")

    assert seconds == 45
