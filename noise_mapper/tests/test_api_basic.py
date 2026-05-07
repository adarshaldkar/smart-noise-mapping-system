import os
import sys
import unittest
import importlib

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "api"))

api_main = importlib.import_module("api.main")

app = api_main.app
measurements_list_to_field_value = api_main.measurements_list_to_field_value


class TestCode(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        self.client.testing = True

    def test_index_route(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"/noisemap", response.data)

    def test_dashboard_route(self):
        response = self.client.get("/dashboard")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Noise Mapper", response.data)

    def test_measurements_list_to_field_value(self):
        measurements = [
            {"lat": 1, "lon": 2, "sound": 3},
            {"lat": 4, "lon": 5, "sound": 6},
            {"lat": 7, "lon": 8, "sound": 9},
        ]
        output = measurements_list_to_field_value(measurements, "sound")
        self.assertEqual(output, [3, 6, 9])


if __name__ == '__main__':
    unittest.main()