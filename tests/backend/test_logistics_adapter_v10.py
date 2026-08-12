from __future__ import annotations

import csv
import io
import json
import unittest

from app.backend.logistics_adapter import (
    LogisticsValidationError,
    parse_logistics,
    parse_logistics_csv,
    parse_logistics_json,
    validate_logistics_nodes,
)


def rows():
    return [
        {
            "package_alias": "PKG-DEMO-001",
            "node_id": f"N{i}",
            "node_type": kind,
            "event_time": f"2026-08-12T0{i}:00:00+08:00",
            "location_alias": f"LOC-{i}",
            "device_alias": "DEVICE-DEMO",
            "status": "CAPTURED",
            "notes": "",
        }
        for i, kind in enumerate(("PICKUP", "SORTING", "DELIVERY"), start=1)
    ]


class LogisticsAdapterTests(unittest.TestCase):
    def test_json_list(self):
        self.assertEqual(len(parse_logistics_json(json.dumps(rows()).encode())), 3)

    def test_json_nodes_wrapper(self):
        parsed = parse_logistics_json(json.dumps({"nodes": rows()}).encode())
        self.assertEqual([x["node_id"] for x in parsed], ["N1", "N2", "N3"])

    def test_csv(self):
        stream = io.StringIO(newline="")
        writer = csv.DictWriter(stream, fieldnames=list(rows()[0]))
        writer.writeheader()
        writer.writerows(rows())
        self.assertEqual(len(parse_logistics_csv(stream.getvalue().encode())), 3)

    def test_dispatch_json(self):
        self.assertEqual(
            parse_logistics(json.dumps(rows()).encode(), ".json")[0]["node_type"],
            "PICKUP",
        )

    def test_dispatch_csv(self):
        stream = io.StringIO(newline="")
        writer = csv.DictWriter(stream, fieldnames=list(rows()[0]))
        writer.writeheader()
        writer.writerows(rows())
        self.assertEqual(
            parse_logistics(stream.getvalue().encode(), "CSV")[-1]["node_type"],
            "DELIVERY",
        )

    def test_missing_required_field(self):
        data = rows()
        del data[0]["device_alias"]
        with self.assertRaises(LogisticsValidationError) as caught:
            validate_logistics_nodes(data)
        self.assertEqual(caught.exception.field, "device_alias")

    def test_rejects_phone_field(self):
        data = rows()
        data[0]["phone"] = "13800000000"
        with self.assertRaises(LogisticsValidationError):
            validate_logistics_nodes(data)

    def test_rejects_tracking_number_field(self):
        data = rows()
        data[0]["tracking_number"] = "SECRET"
        with self.assertRaises(LogisticsValidationError):
            validate_logistics_nodes(data)

    def test_rejects_invalid_node_type(self):
        data = rows()
        data[0]["node_type"] = "UNKNOWN"
        with self.assertRaises(LogisticsValidationError):
            validate_logistics_nodes(data)

    def test_accepts_custom_node_type(self):
        data = rows()
        data[0]["node_type"] = "CUSTOM"
        self.assertEqual(validate_logistics_nodes(data)[0]["node_type"], "CUSTOM")

    def test_requires_timezone(self):
        data = rows()
        data[0]["event_time"] = "2026-08-12T01:00:00"
        with self.assertRaises(LogisticsValidationError):
            validate_logistics_nodes(data)

    def test_rejects_duplicate_node(self):
        data = rows()
        data[1]["node_id"] = "N1"
        with self.assertRaises(LogisticsValidationError):
            validate_logistics_nodes(data)

    def test_rejects_mixed_package_aliases(self):
        data = rows()
        data[-1]["package_alias"] = "PKG-OTHER"
        with self.assertRaises(LogisticsValidationError):
            validate_logistics_nodes(data)

    def test_rejects_out_of_order_time(self):
        data = rows()
        data[0]["event_time"] = "2026-08-12T09:00:00+08:00"
        with self.assertRaises(LogisticsValidationError):
            validate_logistics_nodes(data)

    def test_rejects_invalid_format(self):
        with self.assertRaises(LogisticsValidationError):
            parse_logistics(b"x", "xml")

    def test_rejects_empty_json(self):
        with self.assertRaises(LogisticsValidationError):
            parse_logistics_json(b"[]")

    def test_normalizes_node_type_case(self):
        data = rows()
        data[0]["node_type"] = "pickup"
        self.assertEqual(validate_logistics_nodes(data)[0]["node_type"], "PICKUP")


if __name__ == "__main__":
    unittest.main()
