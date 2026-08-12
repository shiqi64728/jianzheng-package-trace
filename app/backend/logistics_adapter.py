"""Privacy-minimizing JSON/CSV adapter for structured logistics nodes."""

from __future__ import annotations

import csv
import io
import json
import re
from datetime import datetime
from typing import Any

NODE_TYPES = {"PICKUP", "SORTING", "TRANSIT", "STATION", "DELIVERY", "CUSTOM"}
REQUIRED_FIELDS = (
    "package_alias",
    "node_id",
    "node_type",
    "event_time",
    "location_alias",
    "device_alias",
    "status",
    "notes",
)
FORBIDDEN_FIELDS = {
    "real_name",
    "name",
    "phone",
    "phone_number",
    "mobile",
    "address",
    "full_address",
    "tracking_number",
    "waybill_number",
}
ALIAS_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
NODE_RE = re.compile(r"^N[1-9][0-9]*$")


class LogisticsValidationError(ValueError):
    def __init__(
        self, message: str, *, row: int | None = None, field: str | None = None
    ):
        super().__init__(message)
        self.row = row
        self.field = field


def _iso_time(value: str, row_number: int) -> str:
    text = value.strip()
    if not text:
        raise LogisticsValidationError(
            "event_time is required", row=row_number, field="event_time"
        )
    normalized = text[:-1] + "+00:00" if text.endswith("Z") else text
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise LogisticsValidationError(
            "event_time must be ISO 8601", row=row_number, field="event_time"
        ) from exc
    if parsed.tzinfo is None:
        raise LogisticsValidationError(
            "event_time must include a timezone", row=row_number, field="event_time"
        )
    return parsed.isoformat()


def validate_logistics_nodes(rows: list[dict[str, Any]]) -> list[dict[str, str]]:
    if not rows:
        raise LogisticsValidationError("at least one logistics node is required")
    validated: list[dict[str, str]] = []
    seen: set[str] = set()
    package_alias: str | None = None
    for number, raw in enumerate(rows, start=1):
        if not isinstance(raw, dict):
            raise LogisticsValidationError("each node must be an object", row=number)
        lowered = {str(key).strip().lower() for key in raw}
        forbidden = sorted(lowered & FORBIDDEN_FIELDS)
        if forbidden:
            raise LogisticsValidationError(
                f"privacy-sensitive field is not accepted: {forbidden[0]}",
                row=number,
                field=forbidden[0],
            )
        missing = [field for field in REQUIRED_FIELDS if field not in raw]
        if missing:
            raise LogisticsValidationError(
                f"missing required field: {missing[0]}", row=number, field=missing[0]
            )
        item = {field: str(raw.get(field, "")).strip() for field in REQUIRED_FIELDS}
        for alias_field in ("package_alias", "location_alias", "device_alias"):
            if not ALIAS_RE.fullmatch(item[alias_field]):
                raise LogisticsValidationError(
                    f"{alias_field} must be an anonymous alias",
                    row=number,
                    field=alias_field,
                )
        node_id = item["node_id"].upper()
        if not NODE_RE.fullmatch(node_id):
            raise LogisticsValidationError(
                "node_id must match N1, N2, ...", row=number, field="node_id"
            )
        if node_id in seen:
            raise LogisticsValidationError(
                "duplicate node_id", row=number, field="node_id"
            )
        seen.add(node_id)
        node_type = item["node_type"].upper()
        if node_type not in NODE_TYPES:
            raise LogisticsValidationError(
                f"node_type must be one of {sorted(NODE_TYPES)}",
                row=number,
                field="node_type",
            )
        if not item["status"]:
            raise LogisticsValidationError(
                "status is required", row=number, field="status"
            )
        if len(item["notes"]) > 500:
            raise LogisticsValidationError(
                "notes exceeds 500 characters", row=number, field="notes"
            )
        if package_alias is None:
            package_alias = item["package_alias"]
        elif package_alias != item["package_alias"]:
            raise LogisticsValidationError(
                "all imported nodes must use the same package_alias",
                row=number,
                field="package_alias",
            )
        item["node_id"] = node_id
        item["node_type"] = node_type
        item["event_time"] = _iso_time(item["event_time"], number)
        validated.append(item)

    ordered = sorted(
        validated, key=lambda item: (item["event_time"], int(item["node_id"][1:]))
    )
    if [item["node_id"] for item in ordered] != [item["node_id"] for item in validated]:
        raise LogisticsValidationError(
            "nodes must be ordered by event_time and node_id"
        )
    return validated


def parse_logistics_json(content: bytes) -> list[dict[str, str]]:
    try:
        payload = json.loads(content.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise LogisticsValidationError("invalid UTF-8 JSON") from exc
    rows = payload.get("nodes") if isinstance(payload, dict) else payload
    if not isinstance(rows, list):
        raise LogisticsValidationError("JSON must be a list or an object with nodes[]")
    return validate_logistics_nodes(rows)


def parse_logistics_csv(content: bytes) -> list[dict[str, str]]:
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise LogisticsValidationError("invalid UTF-8 CSV") from exc
    try:
        reader = csv.DictReader(io.StringIO(text, newline=""))
        if reader.fieldnames is None:
            raise LogisticsValidationError("CSV header is required")
        rows = list(reader)
    except csv.Error as exc:
        raise LogisticsValidationError("invalid CSV") from exc
    return validate_logistics_nodes(rows)


def parse_logistics(content: bytes, data_format: str) -> list[dict[str, str]]:
    normalized = data_format.strip().lower().lstrip(".")
    if normalized == "json":
        return parse_logistics_json(content)
    if normalized == "csv":
        return parse_logistics_csv(content)
    raise LogisticsValidationError("format must be json or csv", field="format")
