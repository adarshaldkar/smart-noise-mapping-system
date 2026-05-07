"""Comprehensive test suite for the Noise Mapper API."""

import json
import os
import sys
import unittest
import importlib
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "api"))

api_main = importlib.import_module("api.main")

app = api_main.app
measurements_list_to_field_value = api_main.measurements_list_to_field_value


class TestNoiseMapperAPI(unittest.TestCase):
    def setUp(self):
        self.app = app.test_client()
        self.app.testing = True

    def test_index_route(self):
        response = self.app.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"/noisemap", response.data)

    @patch.object(api_main, "query_points")
    def test_noisemap_route(self, mock_query_points):
        mock_query_points.return_value = [
            {"lat": 41.38, "lon": 2.17, "sound": 0.015, "noise_class": "Traffic", "confidence": 0.91},
            {"lat": 41.39, "lon": 2.18, "sound": 0.012, "noise_class": "Speech", "confidence": 0.82},
            {"lat": 41.40, "lon": 2.19, "sound": 0.018, "noise_class": "Music", "confidence": 0.77},
        ]

        response = self.app.get("/noisemap")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"folium-map", response.data)

    @patch.object(api_main, "query_points")
    def test_heatmap_route(self, mock_query_points):
        mock_query_points.return_value = [
            {"lat": 41.38, "lon": 2.17},
            {"lat": 41.39, "lon": 2.18},
            {"lat": 41.40, "lon": 2.19},
        ]

        response = self.app.get("/heatmap")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"folium-map", response.data)

    @patch.object(api_main, "query_points")
    def test_last_location_route(self, mock_query_points):
        mock_query_points.return_value = [{"lat": 41.38, "lon": 2.17, "sound": 0.015, "time": "2023-01-01T10:00:00Z"}]

        response = self.app.get("/last-location/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"folium-map", response.data)

    @patch.object(api_main, "query_points")
    def test_last_session_route(self, mock_query_points):
        mock_query_points.side_effect = [
            [{"session_uuid": "test-uuid-123"}],
            [
                {"lat": 41.38, "lon": 2.17, "sound": 0.015, "time": "2023-01-01T10:00:00Z"},
                {"lat": 41.39, "lon": 2.18, "sound": 0.012, "time": "2023-01-01T10:01:00Z"},
            ],
        ]

        response = self.app.get("/last-session/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"folium-map", response.data)

    @patch.object(api_main, "query_points")
    def test_api_stats_route(self, mock_query_points):
        mock_query_points.return_value = [
            {"sound": 0.015, "noise_class": "Traffic", "confidence": 0.91, "zero_crossing_rate": 0.04, "spectral_centroid": 465.6},
            {"sound": 0.012, "noise_class": "Traffic", "confidence": 0.82, "zero_crossing_rate": 0.05, "spectral_centroid": 500.1},
        ]

        response = self.app.get("/api/stats")
        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.data)
        self.assertIn("avg_db", payload)
        self.assertIn("total_samples", payload)
        self.assertEqual(payload["total_samples"], 2)

    @patch.object(api_main, "query_points")
    def test_api_samples_route(self, mock_query_points):
        mock_query_points.return_value = [
            {"lat": 41.38, "lon": 2.17, "sound": 0.015, "noise_class": "Traffic"},
        ]

        response = self.app.get("/api/samples?hours=1&class=all&min_conf=0")
        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.data)
        self.assertEqual(len(payload), 1)

    @patch.object(api_main, "INFLUXDBCLIENT")
    def test_api_inject_demo_route(self, mock_influx):
        mock_influx.write_points.return_value = True

        response = self.app.post("/api/inject-demo")
        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.data)
        self.assertEqual(payload["status"], "success")

    @patch.object(api_main, "INFLUXDBCLIENT")
    def test_api_clear_demo_route(self, mock_influx):
        mock_influx.query.return_value = []

        response = self.app.post("/api/clear-demo")
        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.data)
        self.assertEqual(payload["status"], "success")


class TestDataProcessingFunctions(unittest.TestCase):
    def test_measurements_list_to_field_value(self):
        measurements = [
            {"lat": 41.38, "lon": 2.17, "sound": 0.015},
            {"lat": 41.39, "lon": 2.18, "sound": 0.012},
            {"lat": 41.40, "lon": 2.19, "sound": 0.018},
        ]

        self.assertEqual(measurements_list_to_field_value(measurements, "sound"), [0.015, 0.012, 0.018])


if __name__ == '__main__':
    unittest.main()