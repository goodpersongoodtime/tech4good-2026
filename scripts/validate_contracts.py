#!/usr/bin/env python3
"""Validate the OpenAPI document and every frontend fixture against it."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any
import yaml
from jsonschema import Draft202012Validator, FormatChecker
from openapi_spec_validator import validate_spec


ROOT = Path(__file__).resolve().parents[1]
OPENAPI_PATH = ROOT / "docs" / "openapi.yaml"

FIXTURE_SCHEMAS = {
    "mocks/auth/signup.success.json": "AuthResponse",
    "mocks/auth/login.success.json": "AuthResponse",
    "mocks/profile/me.success.json": "UserProfile",
    "mocks/places/search.success.json": "PlaceSearchResponse",
    "mocks/routes/transit.accessible.json": "RouteSearchResponse",
    "mocks/routes/transit.caution.json": "RouteSearchResponse",
    "mocks/routes/taxi.success.json": "RouteSearchResponse",
    "mocks/routes/walk.success.json": "RouteSearchResponse",
    "mocks/routes/no-accessible-route.json": "RouteSearchResponse",
    "mocks/navigation/start.success.json": "NavigationSession",
    "mocks/navigation/position.reroute-suggested.json": "NavigationUpdate",
    "mocks/navigation/reroute.missed-transit.success.json": "NavigationSession",
    "mocks/navigation/complete.success.json": "NavigationCompletion",
    "mocks/errors/upstream-unavailable.json": "ErrorResponse",
    "mocks/errors/rate-limited.json": "ErrorResponse",
    "mocks/errors/email-already-exists.json": "ErrorResponse",
    "mocks/errors/invalid-credentials.json": "ErrorResponse",
    "mocks/errors/profile-required.json": "ErrorResponse",
    "mocks/errors/route-expired.json": "ErrorResponse",
}


def load_yaml(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as file:
        value = yaml.safe_load(file)
    if not isinstance(value, dict):
        raise AssertionError(f"{path} must contain a mapping")
    return value


def load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as file:
        value = json.load(file)
    if not isinstance(value, dict):
        raise AssertionError(f"{path} must contain a JSON object")
    return value


def validate_fixture(
    spec: dict[str, Any], relative_path: str, schema_name: str
) -> dict[str, Any]:
    instance = load_json(ROOT / relative_path)
    schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$ref": f"#/components/schemas/{schema_name}",
        "components": spec["components"],
    }
    validator = Draft202012Validator(
        schema,
        format_checker=FormatChecker(),
    )
    errors = sorted(validator.iter_errors(instance), key=lambda error: list(error.path))
    if errors:
        messages = []
        for error in errors:
            location = ".".join(str(part) for part in error.absolute_path) or "<root>"
            messages.append(f"  - {location}: {error.message}")
        raise AssertionError(
            f"{relative_path} does not match {schema_name}:\n" + "\n".join(messages)
        )
    return instance


def parse_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise AssertionError(f"Timezone offset is required: {value}")
    return parsed


def validate_business_invariants(fixtures: dict[str, dict[str, Any]]) -> None:
    for path, value in fixtures.items():
        if path.startswith("mocks/routes/"):
            generated_at = parse_datetime(value["generatedAt"])
            expires_at = parse_datetime(value["expiresAt"])
            if int((expires_at - generated_at).total_seconds()) != 600:
                raise AssertionError(f"{path}: route fixture TTL must be exactly 600 seconds")

            ranks = [route["rank"] for route in value["routes"]]
            if ranks != sorted(ranks):
                raise AssertionError(f"{path}: routes must be sorted by rank")

    no_route = fixtures["mocks/routes/no-accessible-route.json"]
    if no_route["status"] != "NO_ACCESSIBLE_ROUTE":
        raise AssertionError("No-route fixture must use NO_ACCESSIBLE_ROUTE")
    if no_route["routes"] or "TAXI" not in no_route["fallbackModes"]:
        raise AssertionError("No-route fixture must have no routes and offer TAXI")

    started = fixtures["mocks/navigation/start.success.json"]
    rerouted = fixtures["mocks/navigation/reroute.missed-transit.success.json"]
    if started["sessionId"] != rerouted["sessionId"]:
        raise AssertionError("Reroute fixture must keep the same navigation session")
    if rerouted["routeRevision"] != started["routeRevision"] + 1:
        raise AssertionError("Reroute fixture must increment routeRevision by one")
    if rerouted["route"]["routeId"] == started["route"]["routeId"]:
        raise AssertionError("Reroute fixture must return a new route")

    completion = fixtures["mocks/navigation/complete.success.json"]
    if "coordinate" in json.dumps(completion):
        raise AssertionError("Completion fixture must not persist raw coordinates")


def main() -> None:
    spec = load_yaml(OPENAPI_PATH)
    validate_spec(spec)

    discovered = {
        str(path.relative_to(ROOT))
        for path in (ROOT / "mocks").rglob("*.json")
    }
    expected = set(FIXTURE_SCHEMAS)
    if discovered != expected:
        missing = sorted(expected - discovered)
        unmapped = sorted(discovered - expected)
        raise AssertionError(f"Fixture map mismatch; missing={missing}, unmapped={unmapped}")

    fixtures = {
        path: validate_fixture(spec, path, schema_name)
        for path, schema_name in FIXTURE_SCHEMAS.items()
    }
    validate_business_invariants(fixtures)
    print(f"OpenAPI valid; {len(fixtures)} fixtures valid; invariants valid")


if __name__ == "__main__":
    main()
