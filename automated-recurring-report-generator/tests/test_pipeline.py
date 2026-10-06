"""Meaningful edge cases: calendar boundaries, metric scope and quality gates.

These tests use hand-checked frames and never change the PostgreSQL database.
"""
import json
import os
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from report_pipeline import (
    ReportConfig, build_analysis, calculate_kpis, create_charts, fallback_summary,
    generate_summary, select_period, validate_data, validate_summary,
)


def sample_data():
    # The first delivered order has two items but still contributes one AOV order.
    rows = [
        ("a", "delivered", "2018-07-01 10:00", "2018-07-05 18:00", "2018-07-05", "u1", 2, 100.0, 120.0, 4.0, "current"),
        ("b", "delivered", "2018-07-02 10:00", "2018-07-06 10:00", "2018-07-05", "u1", 1, 50.0, 60.0, None, "current"),
        ("c", "canceled", "2018-07-03 10:00", None, "2018-07-08", "u2", None, None, None, None, "current"),
        ("d", "unavailable", "2018-07-04 10:00", None, "2018-07-08", "u3", None, None, None, None, "current"),
        ("e", "delivered", "2018-06-01 10:00", "2018-06-05 10:00", "2018-06-05", "u4", 1, 0.0, 0.0, 5.0, "previous"),
    ]
    columns = ["order_id", "order_status", "order_purchase_timestamp", "order_delivered_customer_date",
               "order_estimated_delivery_date", "customer_unique_id", "item_count", "merchandise_value",
               "payment_value", "review_score", "period"]
    orders = pd.DataFrame(rows, columns=columns)
    for col in ["order_purchase_timestamp", "order_delivered_customer_date", "order_estimated_delivery_date"]:
        orders[col] = pd.to_datetime(orders[col], format="mixed")
    orders["customer_state"] = "SP"
    orders["freight_value"] = 0
    for col in ("bad_item_rows", "bad_payment_rows", "bad_review_rows"):
        orders[col] = 0
    items = pd.DataFrame({"order_id": ["a", "a", "b", "e"], "order_item_id": [1, 2, 1, 1],
                          "price": [60.0, 40.0, 50.0, 0.0], "category": ["home", "home", "books", "books"],
                          "period": ["current", "current", "current", "previous"]})
    items["order_purchase_timestamp"] = pd.to_datetime(["2018-07-01"] * 2 + ["2018-07-02", "2018-06-01"])
    return {"orders": orders, "items": items, "period": select_period(date(2018, 8, 1), "monthly"),
            "coverage": {"first_purchase": pd.Timestamp("2018-01-01"), "last_purchase": pd.Timestamp("2018-08-29"),
                         "last_delivered_purchase": pd.Timestamp("2018-08-29"), "total_orders": 5, "undated_orders": 0},
            "sql_totals": pd.DataFrame({"period": ["current", "previous"], "gmv": [150.0, 0.0]})}


class CalendarTests(unittest.TestCase):
    def test_leap_year_and_year_boundary(self):
        p = select_period(date(2024, 3, 1), "monthly")
        self.assertEqual((p.start, p.end, p.prior_start), (date(2024, 2, 1), date(2024, 3, 1), date(2024, 1, 1)))
        p = select_period(date(2024, 1, 15), "monthly")
        self.assertEqual(p.start, date(2023, 12, 1))
        self.assertEqual(p.prior_start, date(2023, 11, 1))

    def test_week_on_monday_and_midweek(self):
        monday = select_period(date(2018, 8, 27), "weekly")
        midweek = select_period(date(2018, 8, 29), "weekly")
        self.assertEqual(monday, midweek)
        self.assertEqual(monday.start, date(2018, 8, 20))
        self.assertEqual(monday.end, date(2018, 8, 27))


class MetricTests(unittest.TestCase):
    def test_scope_same_day_on_time_and_missing_reviews(self):
        d = sample_data()
        k = calculate_kpis(d["orders"].loc[d["orders"]["period"].eq("current")])
        self.assertEqual(k["orders"], 4)
        self.assertEqual(k["delivered_orders"], 2)
        self.assertEqual(k["gmv"], 150)
        self.assertEqual(k["aov"], 75)
        self.assertEqual(k["customers"], 3)  # u1 buys twice, not two distinct customers.
        self.assertEqual(k["cancellation_rate"], 25)  # unavailable isn't canceled.
        self.assertEqual(k["on_time_rate"], 50)  # Evening on the promised day is on time.
        self.assertEqual(k["review_score"], 4)
        self.assertEqual(k["review_sample"], 1)
        self.assertEqual(k["payment_total"], 180)

    def test_empty_cohort_is_not_reported_as_zero_gmv(self):
        k = calculate_kpis(sample_data()["orders"].iloc[:0])
        self.assertEqual(k["orders"], 0)
        for metric in ("gmv", "aov", "on_time_rate", "review_score", "payment_total"):
            self.assertIsNone(k[metric])

    def test_zero_baseline_is_na_and_rates_are_points(self):
        a = build_analysis(sample_data())
        k = a["kpis"].set_index("metric")
        self.assertEqual(k.loc["gmv", "change_display"], "N/A")
        self.assertEqual(k.loc["on_time_rate", "change_display"], "-50.0 pp")

    def test_empty_sql_frames_still_generate_all_charts(self):
        d = sample_data()
        d['orders'] = d['orders'].iloc[:0].copy()
        d['items'] = d['items'].iloc[:0].copy()
        # Simulate pandas' dtype for a numeric column from an empty SQL result.
        d['orders']['merchandise_value'] = d['orders']['merchandise_value'].astype(object)
        a = build_analysis(d)
        with tempfile.TemporaryDirectory() as folder:
            paths = create_charts(a, d['period'], Path(folder))
            self.assertEqual(len(paths), 3)
            self.assertTrue(all(p.stat().st_size > 1000 for p in paths))

    def test_invalid_delivery_excluded(self):
        d = sample_data()
        d["orders"].loc[0, "order_delivered_customer_date"] = pd.Timestamp("2018-06-30")
        w = validate_data(d, ReportConfig(ai_mode="off"))
        self.assertTrue(any("invalid delivery" in s for s in w))
        k = calculate_kpis(d["orders"].loc[d["orders"]["period"].eq("current")])
        self.assertEqual(k["on_time_sample"], 1)
        self.assertEqual(k["on_time_rate"], 0)


class QualityTests(unittest.TestCase):
    def test_valid_data_reconciles(self):
        validate_data(sample_data(), ReportConfig(ai_mode="off"))

    def test_duplicate_order_stops_report(self):
        d = sample_data()
        d["orders"] = pd.concat([d["orders"], d["orders"].iloc[:1]], ignore_index=True)
        with self.assertRaisesRegex(ValueError, "duplicate order"):
            validate_data(d, ReportConfig())

    def test_monetary_corruption_stops_report(self):
        d = sample_data()
        d["orders"].loc[0, "bad_item_rows"] = 1
        with self.assertRaisesRegex(ValueError, "Invalid financial"):
            validate_data(d, ReportConfig())

    def test_independent_sql_mismatch_stops_report(self):
        d = sample_data()
        d["sql_totals"].loc[0, "gmv"] = 300.0
        with self.assertRaisesRegex(ValueError, "independent SQL"):
            validate_data(d, ReportConfig())


class SummaryTests(unittest.TestCase):
    def test_fallback_is_labelled_and_serializable(self):
        d = sample_data()
        a = build_analysis(d)
        s = fallback_summary(a, d, [], "test mode")
        self.assertEqual(s["source"], "rule_based")
        self.assertIsNone(s["model"])
        self.assertIn("BRL 150.00", s["what_changed"][0])
        json.dumps(s)
        validate_summary(s)

    def test_bad_model_structure_rejected(self):
        with self.assertRaises(ValueError):
            validate_summary({"headline": "incomplete"})

    def test_missing_key_auto_falls_back_required_fails(self):
        d = sample_data()
        a = build_analysis(d)
        with patch.dict(os.environ, {}, clear=True):
            s = generate_summary(ReportConfig(ai_mode="auto"), a, d, [], [])
            self.assertEqual(s["source"], "rule_based")
            with self.assertRaises(EnvironmentError):
                generate_summary(ReportConfig(ai_mode="required"), a, d, [], [])


if __name__ == "__main__":
    unittest.main()
