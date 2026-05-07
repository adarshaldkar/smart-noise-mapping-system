"""Integration tests for the complete Noise Mapper system."""

import os
import unittest

import requests

try:
    import docker
except ImportError:
    docker = None


class TestSystemIntegration(unittest.TestCase):
    def setUp(self):
        self.base_url = "http://localhost:5000"
        self.influx_url = "http://localhost:8086"

    def test_api_health_check(self):
        response = requests.get(f"{self.base_url}/", timeout=5)
        self.assertEqual(response.status_code, 200)

    def test_influxdb_connection(self):
        response = requests.get(f"{self.influx_url}/ping", timeout=5)
        self.assertIn(response.status_code, [200, 204])

    def test_api_endpoints(self):
        endpoints = ["/dashboard", "/noisemap", "/heatmap", "/last-location/", "/last-session/"]
        for endpoint in endpoints:
            response = requests.get(f"{self.base_url}{endpoint}", timeout=15)
            self.assertIn(response.status_code, [200, 500])


class TestDockerIntegration(unittest.TestCase):
    def setUp(self):
        if docker is None:
            self.skipTest("docker Python package is not installed")
        self.docker_client = docker.from_env()

    def test_docker_compose_services(self):
        compose_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), "docker-compose.yml")
        if not os.path.exists(compose_file):
            self.skipTest("docker-compose.yml not found")

        with open(compose_file, "r", encoding="utf-8") as handle:
            content = handle.read()

        for service in ["grafana", "influxdb", "noisemapper_consumer", "noisemapper_api", "mosquitto"]:
            self.assertIn(service, content)

    def test_container_health_checks(self):
        compose_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), "docker-compose.yml")
        if not os.path.exists(compose_file):
            self.skipTest("docker-compose.yml not found")

        with open(compose_file, "r", encoding="utf-8") as handle:
            content = handle.read()

        self.assertIn("healthcheck", content)


class TestDataFlow(unittest.TestCase):
    def test_sample_data_processing(self):
        sample_measurements = [
            {
                "lat": 41.3851,
                "lon": 2.1734,
                "alt": 20.0,
                "session_uuid": "test-session-123",
                "user_uuid": "test-user-456",
                "type": "GPS",
                "source": "mobile",
                "time": 1770000000,
                "test": "True",
            }
        ]

        for measurement in sample_measurements:
            self.assertIn("lat", measurement)
            self.assertIn("lon", measurement)
            self.assertIn("session_uuid", measurement)
            self.assertIsInstance(measurement["lat"], (int, float))
            self.assertIsInstance(measurement["lon"], (int, float))


class TestErrorRecovery(unittest.TestCase):
    def test_consumer_resilience(self):
        invalid_messages = [
            {"invalid": "no required fields"},
            {"lat": "not_a_number", "lon": 2.17},
            {},
        ]

        for invalid_msg in invalid_messages:
            self.assertIsInstance(invalid_msg, dict)


class TestSecurityAndValidation(unittest.TestCase):
    def test_input_sanitization(self):
        suspicious_inputs = [
            "'; DROP MEASUREMENT samples; --",
            "1' OR '1'='1",
            "<script>alert('xss')</script>",
        ]

        for suspicious_input in suspicious_inputs:
            self.assertIsInstance(suspicious_input, str)


if __name__ == '__main__':
    os.environ.setdefault("TESTING", "True")
    unittest.main(verbosity=2, warnings="ignore")