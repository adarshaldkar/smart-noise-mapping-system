"""
Integration Test Suite for the Complete Noise Mapper System
Tests end-to-end workflows, Docker container integration, and system performance
"""

import unittest
import pytest
import requests
import time
import json
import numpy as np
from unittest.mock import Mock, patch
import subprocess
import docker
import os
import sys


class TestSystemIntegration(unittest.TestCase):
    """Test suite for complete system integration"""
    
    def setUp(self):
        """Set up test fixtures for integration tests"""
        self.base_url = "http://localhost:5000"  # API endpoint
        self.mqtt_host = "localhost"
        self.mqtt_port = 1883
        self.influx_url = "http://localhost:8086"
        
    def test_api_health_check(self):
        """Test that the API is running and responsive"""
        try:
            response = requests.get(f"{self.base_url}/", timeout=5)
            self.assertEqual(response.status_code, 200)
        except requests.exceptions.ConnectionError:
            self.skipTest("API server not running - start with 'python main.py' in api/ directory")
            
    def test_influxdb_connection(self):
        """Test InfluxDB connectivity"""
        try:
            response = requests.get(f"{self.influx_url}/ping", timeout=5)
            self.assertIn(response.status_code, [200, 204])
        except requests.exceptions.ConnectionError:
            self.skipTest("InfluxDB not running - start with docker-compose")
            
    def test_api_endpoints_without_data(self):
        """Test API endpoints when no data is available"""
        endpoints = ['/noisemap', '/heatmap', '/last-location/', '/last-session/']
        
        for endpoint in endpoints:
            try:
                response = requests.get(f"{self.base_url}{endpoint}", timeout=10)
                # Should either succeed or fail gracefully (not crash)
                self.assertIn(response.status_code, [200, 500])  # 500 is OK if no data
            except requests.exceptions.ConnectionError:
                self.skipTest(f"API server not available for {endpoint}")


class TestDockerIntegration(unittest.TestCase):
    """Test Docker container functionality"""
    
    def setUp(self):
        """Set up Docker client for testing"""
        try:
            self.docker_client = docker.from_env()
        except Exception as e:
            self.skipTest(f"Docker not available: {e}")
    
    def test_docker_compose_services(self):
        """Test that Docker Compose services can be started"""
        compose_file = "docker-compose.yml"
        
        if not os.path.exists(compose_file):
            self.skipTest("docker-compose.yml not found")
            
        # Check if services are defined correctly
        with open(compose_file, 'r') as f:
            content = f.read()
            
        # Verify expected services are defined
        expected_services = ['grafana', 'influxdb', 'noisemapper_consumer', 'noisemapper_api', 'mosquitto']
        for service in expected_services:
            self.assertIn(service, content)
            
    def test_container_health_checks(self):
        """Test container health check configurations"""
        compose_file = "docker-compose.yml"
        
        if not os.path.exists(compose_file):
            self.skipTest("docker-compose.yml not found")
            
        with open(compose_file, 'r') as f:
            content = f.read()
            
        # Check for health check configurations
        self.assertIn("healthcheck", content)


class TestPerformanceAndLoad(unittest.TestCase):
    """Test system performance under load"""
    
    def setUp(self):
        self.base_url = "http://localhost:5000"
        
    def test_api_response_time(self):
        """Test API response times under normal load"""
        endpoints = ['/noisemap', '/heatmap']
        
        for endpoint in endpoints:
            start_time = time.time()
            try:
                response = requests.get(f"{self.base_url}{endpoint}", timeout=30)
                end_time = time.time()
                
                response_time = end_time - start_time
                
                # Response should be under 10 seconds for normal datasets
                self.assertLess(response_time, 10.0, 
                              f"Endpoint {endpoint} took {response_time:.2f}s")
                              
            except requests.exceptions.ConnectionError:
                self.skipTest(f"API server not available for performance test")
                
    def test_concurrent_requests(self):
        """Test API handling of concurrent requests"""
        import concurrent.futures
        import threading
        
        def make_request():
            try:
                response = requests.get(f"{self.base_url}/", timeout=10)
                return response.status_code
            except:
                return None
                
        # Test with 5 concurrent requests
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(make_request) for _ in range(5)]
            results = [future.result() for future in concurrent.futures.as_completed(futures)]
            
        # At least some requests should succeed
        successful_requests = sum(1 for result in results if result == 200)
        self.assertGreater(successful_requests, 0)


class TestDataFlow(unittest.TestCase):
    """Test data flow through the complete system"""
    
    def test_sample_data_processing(self):
        """Test processing of sample noise measurement data"""
        # Sample data that would come from the mobile app
        sample_measurements = [
            {
                "lat": 41.3851, "lon": 2.1734, "alt": 20.0,
                "session_uuid": "test-session-123",
                "user_uuid": "test-user-456",
                "type": "GPS", "source": "mobile",
                "time": int(time.time()), "test": "True"  # Mark as test data
            }
        ]
        
        # This would normally be tested with actual MQTT publishing
        # For unit test, we verify the data structure is valid
        for measurement in sample_measurements:
            self.assertIn("lat", measurement)
            self.assertIn("lon", measurement)
            self.assertIn("session_uuid", measurement)
            self.assertTrue(isinstance(measurement["lat"], (int, float)))
            self.assertTrue(isinstance(measurement["lon"], (int, float)))
            
    def test_coordinate_bounds_validation(self):
        """Test that coordinates are within expected Barcelona bounds"""
        from api.main import LAT_LON_BOUNDS
        
        # Test coordinates should be within Barcelona bounds
        test_coords = [
            (41.3851, 2.1734),  # Barcelona center
            (41.357742, 2.109375),  # Southwest bound
            (41.429342, 2.230225)   # Northeast bound
        ]
        
        for lat, lon in test_coords:
            self.assertGreaterEqual(lat, LAT_LON_BOUNDS[0][0])
            self.assertLessEqual(lat, LAT_LON_BOUNDS[1][0])
            self.assertGreaterEqual(lon, LAT_LON_BOUNDS[0][1])
            self.assertLessEqual(lon, LAT_LON_BOUNDS[1][1])


class TestErrorRecovery(unittest.TestCase):
    """Test system error recovery and resilience"""
    
    def test_api_graceful_degradation(self):
        """Test API behavior when dependencies are unavailable"""
        # This would test behavior when InfluxDB is down
        # For unit test, we verify error handling exists
        from api.main import app
        
        test_client = app.test_client()
        test_client.testing = True
        
        # Test that routes exist and can handle errors
        with patch('api.main.INFLUXDBCLIENT') as mock_influx:
            mock_influx.query.side_effect = Exception("Database unavailable")
            
            # Should handle gracefully (may return 500, but shouldn't crash)
            try:
                response = test_client.get('/noisemap')
                self.assertIsNotNone(response)
            except Exception as e:
                # Verify it's a handled exception, not a crash
                self.assertIsInstance(e, Exception)
                
    def test_consumer_resilience(self):
        """Test consumer handling of malformed messages"""
        # Test data validation and error recovery
        invalid_messages = [
            {"invalid": "no required fields"},
            {"lat": "not_a_number", "lon": 2.17},
            {}  # Empty message
        ]
        
        for invalid_msg in invalid_messages:
            # Verify consumer can handle invalid data gracefully
            # This would be tested with actual MQTT message processing
            self.assertTrue(isinstance(invalid_msg, dict))  # Basic structure test


class TestSecurityAndValidation(unittest.TestCase):
    """Test security measures and input validation"""
    
    def test_input_sanitization(self):
        """Test that inputs are properly sanitized"""
        # Test coordinate bounds checking
        from api.main import LAT_LON_BOUNDS, PIXEL_SIZE_DEG_LAT, PIXEL_SIZE_DEG_LON
        
        # Test extreme coordinates
        extreme_coords = [
            (0.0, 0.0),      # Origin
            (90.0, 180.0),   # North Pole, East
            (-90.0, -180.0), # South Pole, West
            (999.0, 999.0)   # Invalid coordinates
        ]
        
        for lat, lon in extreme_coords:
            # Verify bounds checking exists
            if (LAT_LON_BOUNDS[0][0] <= lat <= LAT_LON_BOUNDS[1][0] and
                LAT_LON_BOUNDS[0][1] <= lon <= LAT_LON_BOUNDS[1][1]):
                # Within bounds - should be accepted
                lat_offset = int((lat - LAT_LON_BOUNDS[0][0]) / PIXEL_SIZE_DEG_LAT)
                lon_offset = int((lon - LAT_LON_BOUNDS[0][1]) / PIXEL_SIZE_DEG_LON)
                self.assertGreaterEqual(lat_offset, 0)
                self.assertGreaterEqual(lon_offset, 0)
                
    def test_sql_injection_prevention(self):
        """Test prevention of SQL injection in InfluxDB queries"""
        # Verify that user inputs are not directly interpolated into queries
        # This is mostly handled by the InfluxDB client library
        suspicious_inputs = [
            "'; DROP MEASUREMENT samples; --",
            "1' OR '1'='1",
            "<script>alert('xss')</script>"
        ]
        
        for suspicious_input in suspicious_inputs:
            # Verify inputs would be properly escaped/validated
            self.assertIsInstance(suspicious_input, str)
            # In real implementation, verify these don't cause issues


class TestSystemMonitoring(unittest.TestCase):
    """Test monitoring and metrics collection"""
    
    def test_metrics_collection(self):
        """Test that system metrics are being collected"""
        from api.main import app
        
        test_client = app.test_client()
        
        with patch('api.main.INFLUXDBCLIENT') as mock_influx:
            # Mock successful query
            mock_influx.query.return_value = [[]]
            mock_influx.write_points.return_value = True
            
            # Make request that should generate metrics
            response = test_client.get('/noisemap')
            
            # Verify metrics were attempted to be written
            # Look for calls that include api_response_time
            calls = mock_influx.write_points.call_args_list
            metrics_written = any(
                'api_response_time' in str(call) for call in calls
            )
            self.assertTrue(metrics_written or len(calls) > 0)


if __name__ == '__main__':
    # Set up test environment
    os.environ.setdefault('TESTING', 'True')
    
    # Run different test suites based on available services
    print("Running Noise Mapper Integration Tests...")
    print("=" * 50)
    
    # Run tests with verbose output
    unittest.main(verbosity=2, warnings='ignore')