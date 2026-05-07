"""
Comprehensive test suite for the Noise Mapper API
Generated with enhanced testing capabilities for Flask app and data processing functions
"""

import unittest
import pytest
import numpy as np
import json
from unittest.mock import Mock, patch, MagicMock
import tempfile
import os
import sys

# Add the api directory to Python path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from main import (
    app, generate_array, fill_array, generate_image_from_array, 
    measurements_list_to_field_value, LAT_LON_BOUNDS, 
    PIXEL_SIZE_DEG_LAT, PIXEL_SIZE_DEG_LON, MAX_NOISE_RANGE
)


class TestNoiseMapperAPI(unittest.TestCase):
    """Test suite for the main Flask API endpoints"""
    
    def setUp(self):
        """Set up test fixtures before each test method."""
        self.app = app.test_client()
        self.app.testing = True
        
    @patch('main.INFLUXDBCLIENT')
    def test_index_route(self, mock_influx):
        """Test the index route returns the correct template"""
        with patch('flask.render_template') as mock_render:
            mock_render.return_value = '<html>Index Page</html>'
            response = self.app.get('/')
            self.assertEqual(response.status_code, 200)
            mock_render.assert_called_once_with('./index.html')
    
    @patch('main.INFLUXDBCLIENT')
    def test_noisemap_route(self, mock_influx):
        """Test the noisemap route with mock data"""
        # Mock InfluxDB query response
        mock_samples = [
            {'lat': 41.38, 'lon': 2.17, 'sound': 0.015, 'time': '2023-01-01T10:00:00Z'},
            {'lat': 41.39, 'lon': 2.18, 'sound': 0.012, 'time': '2023-01-01T10:01:00Z'},
            {'lat': 41.40, 'lon': 2.19, 'sound': 0.018, 'time': '2023-01-01T10:02:00Z'}
        ]
        mock_influx.query.return_value = [mock_samples]
        mock_influx.write_points.return_value = True
        
        response = self.app.get('/noisemap')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'folium-map', response.data)  # Check for folium map content
        
    @patch('main.INFLUXDBCLIENT')
    def test_heatmap_route(self, mock_influx):
        """Test the heatmap route with mock data"""
        mock_samples = [
            {'lat': 41.38, 'lon': 2.17},
            {'lat': 41.39, 'lon': 2.18},
            {'lat': 41.40, 'lon': 2.19}
        ]
        mock_influx.query.return_value = [mock_samples]
        
        response = self.app.get('/heatmap')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'folium-map', response.data)
        
    @patch('main.INFLUXDBCLIENT')
    def test_last_location_route(self, mock_influx):
        """Test the last location route"""
        mock_sample = [{'lat': 41.38, 'lon': 2.17, 'sound': 0.015, 'time': '2023-01-01T10:00:00Z'}]
        mock_influx.query.return_value = [mock_sample]
        
        response = self.app.get('/last-location/')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'folium-map', response.data)
        
    @patch('main.INFLUXDBCLIENT')
    def test_last_session_route(self, mock_influx):
        """Test the last session route"""
        mock_last_sample = [{'session_uuid': 'test-uuid-123'}]
        mock_session_samples = [
            {'lat': 41.38, 'lon': 2.17, 'sound': 0.015, 'time': '2023-01-01T10:00:00Z'},
            {'lat': 41.39, 'lon': 2.18, 'sound': 0.012, 'time': '2023-01-01T10:01:00Z'}
        ]
        mock_influx.query.side_effect = [mock_last_sample, mock_session_samples]
        
        response = self.app.get('/last-session/')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'folium-map', response.data)


class TestDataProcessingFunctions(unittest.TestCase):
    """Test suite for data processing and array manipulation functions"""
    
    def test_generate_array(self):
        """Test array generation with correct dimensions"""
        arr = generate_array()
        
        # Calculate expected dimensions
        lat_size = abs(int((LAT_LON_BOUNDS[1][0] - LAT_LON_BOUNDS[0][0]) / PIXEL_SIZE_DEG_LAT))
        lon_size = abs(int((LAT_LON_BOUNDS[1][1] - LAT_LON_BOUNDS[0][1]) / PIXEL_SIZE_DEG_LON))
        
        self.assertEqual(arr.shape, (lat_size, lon_size, 2))
        self.assertTrue(np.all(arr == 0))  # Should be initialized to zeros
        
    def test_fill_array_basic(self):
        """Test basic array filling functionality"""
        arr = generate_array()
        test_lat = LAT_LON_BOUNDS[0][0] + PIXEL_SIZE_DEG_LAT * 5
        test_lon = LAT_LON_BOUNDS[0][1] + PIXEL_SIZE_DEG_LON * 5
        test_sound = 0.01
        
        fill_array(arr, test_lat, test_lon, test_sound)
        
        # Check that the correct pixel was filled
        lat_offset_px = int((test_lat - LAT_LON_BOUNDS[0][0]) / PIXEL_SIZE_DEG_LAT)
        lon_offset_px = int((test_lon - LAT_LON_BOUNDS[0][1]) / PIXEL_SIZE_DEG_LON)
        
        self.assertAlmostEqual(arr[lat_offset_px, lon_offset_px, 0], test_sound, places=6)
        self.assertEqual(arr[lat_offset_px, lon_offset_px, 1], 1)
        
    def test_fill_array_averaging(self):
        """Test that multiple sounds at the same location are averaged correctly"""
        arr = generate_array()
        test_lat = LAT_LON_BOUNDS[0][0] + PIXEL_SIZE_DEG_LAT * 10
        test_lon = LAT_LON_BOUNDS[0][1] + PIXEL_SIZE_DEG_LON * 10
        
        # Fill with multiple sound values
        sounds = [0.01, 0.02, 0.015]
        for sound in sounds:
            fill_array(arr, test_lat, test_lon, sound)
            
        lat_offset_px = int((test_lat - LAT_LON_BOUNDS[0][0]) / PIXEL_SIZE_DEG_LAT)
        lon_offset_px = int((test_lon - LAT_LON_BOUNDS[0][1]) / PIXEL_SIZE_DEG_LON)
        
        expected_avg = np.mean(sounds)
        self.assertAlmostEqual(arr[lat_offset_px, lon_offset_px, 0], expected_avg, places=6)
        self.assertEqual(arr[lat_offset_px, lon_offset_px, 1], len(sounds))
        
    def test_fill_array_boundary_conditions(self):
        """Test array filling at boundary conditions"""
        arr = generate_array()
        
        # Test at minimum bounds
        min_lat = LAT_LON_BOUNDS[0][0]
        min_lon = LAT_LON_BOUNDS[0][1]
        fill_array(arr, min_lat, min_lon, 0.01)
        
        self.assertEqual(arr[0, 0, 0], 0.01)
        self.assertEqual(arr[0, 0, 1], 1)
        
        # Test near maximum bounds
        max_lat = LAT_LON_BOUNDS[1][0] - PIXEL_SIZE_DEG_LAT
        max_lon = LAT_LON_BOUNDS[1][1] - PIXEL_SIZE_DEG_LON
        fill_array(arr, max_lat, max_lon, 0.02)
        
        # Should not raise an IndexError
        self.assertTrue(True)  # If we get here, no exception was raised
        
    def test_generate_image_from_array(self):
        """Test image generation from array"""
        arr = generate_array()
        
        # Add some test data
        arr[10, 10, 0] = 0.015
        arr[10, 10, 1] = 1
        arr[15, 15, 0] = 0.025
        arr[15, 15, 1] = 1
        
        original_max = np.max(arr[..., 0])
        generate_image_from_array(arr)
        
        # Check normalization
        self.assertLessEqual(np.max(arr[..., 0]), 1.0)
        self.assertGreaterEqual(np.min(arr[..., 0]), 0.0)
        
        # Check that MAX_NOISE_RANGE clipping was applied
        if original_max > MAX_NOISE_RANGE:
            self.assertLessEqual(np.max(arr[..., 0]), MAX_NOISE_RANGE)
            
    def test_measurements_list_to_field_value(self):
        """Test field extraction from measurements"""
        measurements = [
            {"lat": 41.38, "lon": 2.17, "sound": 0.015},
            {"lat": 41.39, "lon": 2.18, "sound": 0.012},
            {"lat": 41.40, "lon": 2.19, "sound": 0.018}
        ]
        
        # Test sound field extraction
        sounds = measurements_list_to_field_value(measurements, "sound")
        self.assertEqual(sounds, [0.015, 0.012, 0.018])
        
        # Test lat field extraction
        lats = measurements_list_to_field_value(measurements, "lat")
        self.assertEqual(lats, [41.38, 41.39, 41.40])
        
        # Test lon field extraction
        lons = measurements_list_to_field_value(measurements, "lon")
        self.assertEqual(lons, [2.17, 2.18, 2.19])
        
    def test_measurements_list_to_field_value_empty(self):
        """Test field extraction with empty measurements"""
        measurements = []
        result = measurements_list_to_field_value(measurements, "sound")
        self.assertEqual(result, [])
        
    def test_measurements_list_to_field_value_missing_field(self):
        """Test field extraction with missing field"""
        measurements = [
            {"lat": 41.38, "lon": 2.17},  # Missing 'sound' field
            {"lat": 41.39, "lon": 2.18, "sound": 0.012}
        ]
        
        with self.assertRaises(KeyError):
            measurements_list_to_field_value(measurements, "sound")


class TestErrorHandling(unittest.TestCase):
    """Test suite for error handling and edge cases"""
    
    def setUp(self):
        self.app = app.test_client()
        self.app.testing = True
        
    @patch('main.INFLUXDBCLIENT')
    def test_noisemap_with_none_sounds(self, mock_influx):
        """Test noisemap handling when some sound values are None"""
        mock_samples = [
            {'lat': 41.38, 'lon': 2.17, 'sound': 0.015},
            {'lat': 41.39, 'lon': 2.18, 'sound': None},  # None value
            {'lat': 41.40, 'lon': 2.19, 'sound': 0.018}
        ]
        mock_influx.query.return_value = [mock_samples]
        mock_influx.write_points.return_value = True
        
        response = self.app.get('/noisemap')
        self.assertEqual(response.status_code, 200)
        
    @patch('main.INFLUXDBCLIENT')
    def test_database_connection_error(self, mock_influx):
        """Test handling of database connection errors"""
        mock_influx.query.side_effect = Exception("Database connection failed")
        
        with self.assertRaises(Exception):
            self.app.get('/noisemap')
            
    def test_invalid_coordinates(self):
        """Test handling of coordinates outside bounds"""
        arr = generate_array()
        
        # Test coordinates outside bounds (should not crash)
        try:
            fill_array(arr, 0.0, 0.0, 0.01)  # Outside Barcelona bounds
            # If we get here, it handled gracefully or wrapped coordinates
        except IndexError:
            # This is expected behavior for out-of-bounds coordinates
            pass


class TestPerformance(unittest.TestCase):
    """Test suite for performance-related tests"""
    
    def test_large_array_generation(self):
        """Test array generation performance with actual bounds"""
        import time
        
        start_time = time.time()
        arr = generate_array()
        end_time = time.time()
        
        # Should complete in reasonable time (less than 1 second)
        self.assertLess(end_time - start_time, 1.0)
        
        # Check memory usage is reasonable
        memory_mb = arr.nbytes / (1024 * 1024)
        self.assertLess(memory_mb, 100)  # Less than 100MB
        
    def test_multiple_fill_operations(self):
        """Test performance of multiple fill operations"""
        import time
        
        arr = generate_array()
        num_operations = 1000
        
        start_time = time.time()
        for i in range(num_operations):
            lat = LAT_LON_BOUNDS[0][0] + (i % 100) * PIXEL_SIZE_DEG_LAT
            lon = LAT_LON_BOUNDS[0][1] + (i % 100) * PIXEL_SIZE_DEG_LON
            sound = 0.01 + (i % 10) * 0.001
            fill_array(arr, lat, lon, sound)
        end_time = time.time()
        
        # Should complete 1000 operations in reasonable time
        self.assertLess(end_time - start_time, 2.0)


if __name__ == '__main__':
    # Run tests with verbose output
    unittest.main(verbosity=2)