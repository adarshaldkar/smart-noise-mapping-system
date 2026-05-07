"""
Comprehensive test suite for the Noise Mapper Consumer
Tests MQTT message processing, audio handling, and InfluxDB integration
"""

import unittest
import pytest
import json
import numpy as np
import tempfile
import os
import sys
from unittest.mock import Mock, patch, MagicMock, call
import uuid
from io import BytesIO

# Add the consumer directory to Python path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Mock dependencies before importing
sys.modules['paho.mqtt.client'] = Mock()
sys.modules['moviepy.editor'] = Mock()
sys.modules['audio2numpy'] = Mock()


class TestNoiseMapperConsumer(unittest.TestCase):
    """Test suite for the MQTT consumer and audio processing"""
    
    def setUp(self):
        """Set up test fixtures before each test method."""
        # Import after mocking dependencies
        global main, on_message, mp4_audio_to_arr
        import main
        from main import on_message, mp4_audio_to_arr
        
        self.mock_client = Mock()
        self.mock_userdata = Mock()
        
        # Reset global point dictionary
        main.point = {}
        
    def create_mock_message(self, topic, payload):
        """Helper to create mock MQTT message"""
        message = Mock()
        message.topic = topic
        if isinstance(payload, dict):
            message.payload = Mock()
            message.payload.decode.return_value = json.dumps(payload)
        else:
            message.payload = payload
        return message
        
    def test_position_message_processing(self):
        """Test processing of position data messages"""
        # Test position message
        pos_data = {
            "lat": 41.38,
            "lon": 2.17,
            "alt": 100.5,
            "session_uuid": "test-session-123",
            "user_uuid": "test-user-456",
            "type": "GPS",
            "source": "mobile",
            "time": 1234567890,
            "test": "False"
        }
        
        message = self.create_mock_message("pos", pos_data)
        
        with patch('main.INFLUXDBCLIENT') as mock_influx:
            on_message(self.mock_client, self.mock_userdata, message)
            
            # Check that position data was stored correctly
            time_key = pos_data["time"]
            self.assertIn(time_key, main.point)
            self.assertEqual(main.point[time_key]["lat"], 41.38)
            self.assertEqual(main.point[time_key]["lon"], 2.17)
            self.assertEqual(main.point[time_key]["alt"], 100.5)
            self.assertEqual(main.point[time_key]["session_uuid"], "test-session-123")
            
    @patch('main.mp4_audio_to_arr')
    def test_audio_message_processing(self, mock_audio_converter):
        """Test processing of audio data messages"""
        # Mock audio conversion
        mock_audio_converter.return_value = np.array([0.1, 0.2, -0.1, -0.2, 0.15])
        
        # Create audio message (topic is timestamp)
        audio_data = b"fake_mp4_audio_data"
        message = self.create_mock_message("1234567890", audio_data)
        
        with patch('main.INFLUXDBCLIENT') as mock_influx:
            on_message(self.mock_client, self.mock_userdata, message)
            
            # Check that audio was processed and sound level calculated
            time_key = 1234567890
            self.assertIn(time_key, main.point)
            expected_sound = np.mean(np.abs(mock_audio_converter.return_value))
            self.assertEqual(main.point[time_key]["sound"], expected_sound)
            
    @patch('main.mp4_audio_to_arr')
    def test_complete_data_point_influx_write(self, mock_audio_converter):
        """Test complete data point writing to InfluxDB"""
        mock_audio_converter.return_value = np.array([0.1, 0.2, -0.1])
        
        # First send position data
        pos_data = {
            "lat": 41.38,
            "lon": 2.17,
            "alt": 100.5,
            "session_uuid": "test-session-123",
            "user_uuid": "test-user-456",
            "type": "GPS",
            "source": "mobile",
            "time": 1234567890,
            "test": "False"
        }
        pos_message = self.create_mock_message("pos", pos_data)
        
        # Then send audio data
        audio_message = self.create_mock_message("1234567890", b"fake_audio")
        
        with patch('main.INFLUXDBCLIENT') as mock_influx:
            mock_influx.write_points.return_value = True
            
            # Process position message
            on_message(self.mock_client, self.mock_userdata, pos_message)
            
            # Process audio message (should trigger InfluxDB write)
            on_message(self.mock_client, self.mock_userdata, audio_message)
            
            # Verify InfluxDB write was called with correct data
            mock_influx.write_points.assert_called_once()
            call_args = mock_influx.write_points.call_args
            
            # Check the point structure
            point_data = call_args[0][0][0]  # First argument, first point
            self.assertEqual(point_data["measurement"], "samples")
            self.assertEqual(point_data["fields"]["lat"], 41.38)
            self.assertEqual(point_data["fields"]["lon"], 2.17)
            self.assertEqual(point_data["fields"]["alt"], 100.5)
            self.assertIn("sound", point_data["fields"])
            
            # Check tags
            tags = call_args[1]["tags"]
            self.assertEqual(tags["session_uuid"], "test-session-123")
            self.assertEqual(tags["user_uuid"], "test-user-456")
            self.assertEqual(tags["type"], "GPS")
            self.assertEqual(tags["source"], "mobile")
            self.assertEqual(tags["test"], "False")
            
    def test_partial_data_no_influx_write(self):
        """Test that incomplete data points don't trigger InfluxDB writes"""
        # Send only position data (no audio)
        pos_data = {
            "lat": 41.38,
            "lon": 2.17,
            "alt": 100.5,
            "session_uuid": "test-session-123",
            "user_uuid": "test-user-456",
            "type": "GPS",
            "source": "mobile",
            "time": 1234567890,
            "test": "False"
        }
        message = self.create_mock_message("pos", pos_data)
        
        with patch('main.INFLUXDBCLIENT') as mock_influx:
            on_message(self.mock_client, self.mock_userdata, message)
            
            # Should not call write_points since audio data is missing
            mock_influx.write_points.assert_not_called()
            
            # Data should still be stored in point dictionary
            self.assertIn(1234567890, main.point)
            self.assertEqual(len(main.point[1234567890].keys()), 8)  # 9 total - 1 for sound
            
    @patch('main.mp4_audio_to_arr')
    def test_audio_conversion_error_handling(self, mock_audio_converter):
        """Test handling of audio conversion errors"""
        # Mock audio conversion to raise an exception
        mock_audio_converter.side_effect = Exception("Audio conversion failed")
        
        # First add position data
        main.point[1234567890] = {
            "lat": 41.38, "lon": 2.17, "alt": 100.5,
            "session_uuid": "test-session", "user_uuid": "test-user",
            "type": "GPS", "source": "mobile", "test": "False"
        }
        
        # Then send audio message that should fail
        audio_message = self.create_mock_message("1234567890", b"corrupted_audio")
        
        with patch('main.INFLUXDBCLIENT') as mock_influx, \
             patch('main.logging') as mock_logging:
            
            on_message(self.mock_client, self.mock_userdata, audio_message)
            
            # Should log error and remove the point
            mock_logging.error.assert_called()
            self.assertNotIn(1234567890, main.point)
            mock_influx.write_points.assert_not_called()


class TestAudioProcessing(unittest.TestCase):
    """Test suite for audio processing functions"""
    
    @patch('main.AudioFileClip')
    @patch('main.a2n.audio_from_file')
    @patch('main.os.remove')
    @patch('builtins.open')
    @patch('main.uuid.uuid4')
    def test_mp4_audio_to_arr(self, mock_uuid, mock_open, mock_remove, 
                             mock_audio_from_file, mock_audioclip):
        """Test MP4 to audio array conversion"""
        from main import mp4_audio_to_arr
        
        # Mock UUID generation
        mock_uuid.return_value = "test-filename"
        
        # Mock file operations
        mock_file = Mock()
        mock_open.return_value.__enter__.return_value = mock_file
        
        # Mock audio processing
        mock_clip = Mock()
        mock_audioclip.return_value = mock_clip
        mock_audio_from_file.return_value = (np.array([0.1, 0.2, -0.1]), 44100)
        
        # Test conversion
        test_audio_data = b"fake_mp4_data"
        result = mp4_audio_to_arr(test_audio_data)
        
        # Verify file operations
        mock_file.write.assert_called_once_with(test_audio_data)
        mock_clip.write_audiofile.assert_called_once_with("test-filename.mp3")
        
        # Verify cleanup
        self.assertEqual(mock_remove.call_count, 2)  # Remove both mp4 and mp3
        
        # Verify result
        self.assertTrue(isinstance(result, np.ndarray))
        
    @patch('main.AudioFileClip')
    def test_mp4_audio_to_arr_error_handling(self, mock_audioclip):
        """Test error handling in audio conversion"""
        from main import mp4_audio_to_arr
        
        # Mock AudioFileClip to raise an exception
        mock_audioclip.side_effect = Exception("Invalid audio format")
        
        with self.assertRaises(Exception):
            mp4_audio_to_arr(b"invalid_audio_data")


class TestDataValidation(unittest.TestCase):
    """Test suite for data validation and edge cases"""
    
    def setUp(self):
        import main
        self.main = main
        main.point = {}
        
    def test_missing_required_fields_position(self):
        """Test handling of position messages with missing required fields"""
        from main import on_message
        
        # Missing latitude
        incomplete_pos_data = {
            "lon": 2.17,
            "alt": 100.5,
            "session_uuid": "test-session-123",
            "user_uuid": "test-user-456",
            "type": "GPS",
            "source": "mobile",
            "time": 1234567890,
            "test": "False"
        }
        
        message = self.create_mock_message("pos", incomplete_pos_data)
        
        with patch('main.INFLUXDBCLIENT') as mock_influx:
            # Should handle gracefully (might store None for missing lat)
            on_message(Mock(), Mock(), message)
            
            # Check that data was still processed
            self.assertIn(1234567890, self.main.point)
            
    def create_mock_message(self, topic, payload):
        """Helper to create mock MQTT message"""
        message = Mock()
        message.topic = topic
        if isinstance(payload, dict):
            message.payload = Mock()
            message.payload.decode.return_value = json.dumps(payload)
        else:
            message.payload = payload
        return message
        
    def test_invalid_json_handling(self):
        """Test handling of invalid JSON in position messages"""
        from main import on_message
        
        message = Mock()
        message.topic = "pos"
        message.payload = Mock()
        message.payload.decode.return_value = "invalid json data"
        
        with patch('main.INFLUXDBCLIENT') as mock_influx, \
             patch('main.logging') as mock_logging:
            
            # Should handle JSON decode error gracefully
            try:
                on_message(Mock(), Mock(), message)
            except json.JSONDecodeError:
                pass  # Expected behavior
                
    def test_duplicate_timestamps(self):
        """Test handling of multiple messages with same timestamp"""
        from main import on_message
        
        # First position message
        pos_data1 = {
            "lat": 41.38, "lon": 2.17, "alt": 100.5,
            "session_uuid": "session1", "user_uuid": "user1",
            "type": "GPS", "source": "mobile", "time": 1234567890,
            "test": "False"
        }
        
        # Second position message with same timestamp but different session
        pos_data2 = {
            "lat": 41.39, "lon": 2.18, "alt": 101.0,
            "session_uuid": "session2", "user_uuid": "user2", 
            "type": "GPS", "source": "mobile", "time": 1234567890,
            "test": "False"
        }
        
        message1 = self.create_mock_message("pos", pos_data1)
        message2 = self.create_mock_message("pos", pos_data2)
        
        with patch('main.INFLUXDBCLIENT') as mock_influx:
            on_message(Mock(), Mock(), message1)
            on_message(Mock(), Mock(), message2)
            
            # Second message should overwrite the first
            self.assertEqual(self.main.point[1234567890]["session_uuid"], "session2")
            self.assertEqual(self.main.point[1234567890]["lat"], 41.39)


class TestIntegration(unittest.TestCase):
    """Integration tests for complete workflows"""
    
    def setUp(self):
        import main
        self.main = main
        main.point = {}
        
    def create_mock_message(self, topic, payload):
        """Helper to create mock MQTT message"""
        message = Mock()
        message.topic = topic
        if isinstance(payload, dict):
            message.payload = Mock()
            message.payload.decode.return_value = json.dumps(payload)
        else:
            message.payload = payload
        return message
        
    @patch('main.mp4_audio_to_arr')
    def test_full_workflow_multiple_points(self, mock_audio_converter):
        """Test complete workflow with multiple data points"""
        from main import on_message
        
        mock_audio_converter.return_value = np.array([0.1, 0.2, -0.1])
        
        # Create multiple test data points
        test_points = [
            {
                "pos": {"lat": 41.38, "lon": 2.17, "alt": 100.5, "time": 1000},
                "audio": b"audio1"
            },
            {
                "pos": {"lat": 41.39, "lon": 2.18, "alt": 101.0, "time": 2000},
                "audio": b"audio2"
            },
            {
                "pos": {"lat": 41.40, "lon": 2.19, "alt": 102.0, "time": 3000},
                "audio": b"audio3"
            }
        ]
        
        for point_data in test_points:
            point_data["pos"].update({
                "session_uuid": "test-session", "user_uuid": "test-user",
                "type": "GPS", "source": "mobile", "test": "False"
            })
        
        with patch('main.INFLUXDBCLIENT') as mock_influx:
            mock_influx.write_points.return_value = True
            
            for point_data in test_points:
                # Send position message
                pos_message = self.create_mock_message("pos", point_data["pos"])
                on_message(Mock(), Mock(), pos_message)
                
                # Send audio message
                audio_message = self.create_mock_message(str(point_data["pos"]["time"]), point_data["audio"])
                on_message(Mock(), Mock(), audio_message)
            
            # Should have written 3 points to InfluxDB
            self.assertEqual(mock_influx.write_points.call_count, 3)
            
            # Point dictionary should be empty (all points processed)
            self.assertEqual(len(self.main.point), 0)


if __name__ == '__main__':
    # Run tests with verbose output
    unittest.main(verbosity=2)