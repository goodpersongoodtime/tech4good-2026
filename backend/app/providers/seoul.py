from dataclasses import dataclass
from time import monotonic
from typing import Any
from urllib.parse import quote

import httpx

from app.errors import ApiError
from app.models import DataConfidence, FacilityStatus


@dataclass(frozen=True)
class SeoulElevator:
    status: FacilityStatus
    location_description: str | None
    confidence: DataConfidence = DataConfidence.VERIFIED


class SeoulDataClient:
    elevator_base_url = "http://openapi.seoul.go.kr:8088"
    subway_base_url = "http://swopenAPI.seoul.go.kr/api/subway"

    def __init__(
        self,
        api_key: str,
        subway_api_key: str,
        client: httpx.AsyncClient,
        elevator_cache_ttl_sec: int = 600,
    ) -> None:
        self.api_key = api_key
        self.subway_api_key = subway_api_key
        self.client = client
        self.elevator_cache_ttl_sec = elevator_cache_ttl_sec
        self._elevator_rows: list[dict[str, Any]] | None = None
        self._elevator_rows_expires_at = 0.0

    async def get_elevator(self, station_name: str) -> SeoulElevator | None:
        rows = await self._get_elevator_rows()
        expected = self._station_key(station_name)
        for row in rows:
            if not isinstance(row, dict):
                continue
            actual = self._station_key(str(row.get("stnNm") or row.get("STN_NM") or ""))
            if actual == expected:
                location = (
                    row.get("dtlLoc")
                    or row.get("DTL_LOC")
                    or row.get("fcltLoc")
                    or row.get("dtlPstn")
                )
                return SeoulElevator(
                    status=FacilityStatus.AVAILABLE,
                    location_description=str(location) if location else None,
                )
        return None

    async def _get_elevator_rows(self) -> list[dict[str, Any]]:
        now = monotonic()
        if self._elevator_rows is not None and now < self._elevator_rows_expires_at:
            return self._elevator_rows
        url = f"{self.elevator_base_url}/{self.api_key}/json/getFcElvtr/1/1000"
        payload = await self._get_json(url)
        legacy_rows = (payload.get("getFcElvtr") or {}).get("row", [])
        current_items = (
            ((payload.get("response") or {}).get("body") or {}).get("items") or {}
        )
        current_rows = (
            current_items.get("item", []) if isinstance(current_items, dict) else []
        )
        raw_rows = legacy_rows or current_rows
        self._elevator_rows = [row for row in raw_rows if isinstance(row, dict)]
        self._elevator_rows_expires_at = now + self.elevator_cache_ttl_sec
        return self._elevator_rows

    async def get_next_arrival_sec(self, station_name: str) -> int | None:
        encoded = quote(self._station_key(station_name), safe="")
        url = (
            f"{self.subway_base_url}/{self.subway_api_key}/json/"
            f"realtimeStationArrival/0/20/{encoded}"
        )
        payload = await self._get_json(url)
        values = []
        for row in payload.get("realtimeArrivalList", []):
            try:
                value = int(row.get("barvlDt"))
            except (AttributeError, TypeError, ValueError):
                continue
            if value >= 0:
                values.append(value)
        return min(values) if values else None

    async def _get_json(self, url: str) -> dict[str, Any]:
        try:
            response = await self.client.get(url, headers={"accept": "application/json"})
        except (httpx.TimeoutException, httpx.NetworkError) as error:
            raise self._unavailable() from error
        if response.status_code >= 400:
            raise self._unavailable()
        try:
            payload = response.json()
        except ValueError as error:
            raise self._unavailable() from error
        if not isinstance(payload, dict):
            raise self._unavailable()
        return payload

    @staticmethod
    def _station_key(value: str) -> str:
        return value.strip().removesuffix("역").replace(" ", "")

    @staticmethod
    def _unavailable() -> ApiError:
        return ApiError(
            503,
            "UPSTREAM_UNAVAILABLE",
            "서울시 공공데이터를 불러오지 못했습니다.",
            {"provider": "SEOUL_OPEN_DATA", "retryable": True},
        )
