"""Tests for the Noise Mapper MQTT consumer."""

import json
import os
import sys
import unittest
import importlib.util
from unittest.mock import Mock, patch

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "consumer"))

_CONSUMER_MAIN_PATH = os.path.join(os.path.dirname(__file__), "..", "consumer", "main.py")
_CONSUMER_MAIN_SPEC = importlib.util.spec_from_file_location("noise_mapper_consumer_main_test", _CONSUMER_MAIN_PATH)
main = importlib.util.module_from_spec(_CONSUMER_MAIN_SPEC)
assert _CONSUMER_MAIN_SPEC and _CONSUMER_MAIN_SPEC.loader
_CONSUMER_MAIN_SPEC.loader.exec_module(main)


class TestNoiseMapperConsumer(unittest.TestCase):
    def setUp(self):
        main.point = {}
        self.mock_client = Mock()
        self.mock_userdata = Mock()

    def create_mock_message(self, topic, payload):
        message = Mock()
        message.topic = topic
        message.payload = json.dumps(payload).encode("utf-8") if isinstance(payload, dict) else payload
        return message

    def test_position_message_processing(self):
        pos_data = {
            "lat": 41.38,
            "lon": 2.17,
            "alt": 100.5,
            "session_uuid": "test-session-123",
            "user_uuid": "test-user-456",
            "type": "GPS",
            "source": "mobile",
            "time": 1234567890,
            "test": "False",
        }

        message = self.create_mock_message("pos", pos_data)
        with patch.object(main, "INFLUXDBCLIENT") as mock_influx:
            main.on_message(self.mock_client, self.mock_userdata, message)
            self.assertIn(pos_data["time"], main.point)
            self.assertEqual(main.point[pos_data["time"]]["lat"], 41.38)
            self.assertEqual(main.point[pos_data["time"]]["session_uuid"], "test-session-123")
            mock_influx.write_points.assert_not_called()

    def test_audio_message_processing(self):
        main.point[1234567890] = {
            "lat": 41.38,
            "lon": 2.17,
            "alt": 100.5,
            "session_uuid": "test-session-123",
            "user_uuid": "test-user-456",
            "type": "GPS",
            "source": "mobile",
            "test": "False",
        }

        message = Mock()
        message.topic = "1234567890"
        message.payload = b"fake_mp4_audio_data"

        with patch.object(main, "mp4_audio_to_arr", return_value=(np.array([0.1, 0.2, -0.1, -0.2]), 44100)), \
             patch.object(main, "compute_audio_features", return_value={
                 "sound": 0.15,
                 "sound_db": 46.0,
                 "sound_peak": 0.2,
                 "sound_rms": 0.15,
                 "sound_rms_db": 45.0,
                 "sound_variance": 0.02,
                 "zero_crossing_rate": 0.5,
                 "duration_s": 1.0,
                 "spectral_centroid": 500.0,
                 "spectral_rolloff": 800.0,
             }), \
             patch.object(main, "classify_audio", return_value=("Traffic", 0.91)), \
             patch.object(main, "INFLUXDBCLIENT") as mock_influx:
            mock_influx.write_points.return_value = True

            main.on_message(self.mock_client, self.mock_userdata, message)

            mock_influx.write_points.assert_called_once()
            self.assertNotIn(1234567890, main.point)

    def test_partial_data_no_influx_write(self):
        pos_data = {
            "lat": 41.38,
            "lon": 2.17,
            "alt": 100.5,
            "session_uuid": "test-session-123",
            "user_uuid": "test-user-456",
            "type": "GPS",
            "source": "mobile",
            "time": 1234567890,
            "test": "False",
        }

        message = self.create_mock_message("pos", pos_data)
        with patch.object(main, "INFLUXDBCLIENT") as mock_influx:
            main.on_message(self.mock_client, self.mock_userdata, message)
            mock_influx.write_points.assert_not_called()
            self.assertIn(1234567890, main.point)

    def test_audio_conversion_error_handling(self):
        main.point[1234567890] = {
            "lat": 41.38,
            "lon": 2.17,
            "alt": 100.5,
            "session_uuid": "test-session",
            "user_uuid": "test-user",
            "type": "GPS",
            "source": "mobile",
            "test": "False",
        }

        message = Mock()
        message.topic = "1234567890"
        message.payload = b"corrupted_audio"

        with patch.object(main, "mp4_audio_to_arr", side_effect=Exception("Audio conversion failed")), \
             patch.object(main, "INFLUXDBCLIENT") as mock_influx:
            main.on_message(self.mock_client, self.mock_userdata, message)
            self.assertNotIn(1234567890, main.point)
            mock_influx.write_points.assert_not_called()


class TestAudioProcessing(unittest.TestCase):
    @patch.object(main, "AudioFileClip")
    @patch.object(main.os, "remove")
    @patch("builtins.open")
    @patch.object(main.uuid, "uuid4")
    def test_mp4_audio_to_arr(self, mock_uuid, mock_open, mock_remove, mock_audio_clip):
        mock_uuid.return_value = "test-filename"

        mock_file = Mock()
        mock_open.return_value.__enter__.return_value = mock_file

        mock_clip = Mock()
        mock_clip.fps = 44100
        mock_clip.to_soundarray.return_value = np.array([[0.1, -0.1], [0.2, -0.2]])
        mock_audio_clip.return_value = mock_clip

        audio_arr, sample_rate = main.mp4_audio_to_arr(b"fake_mp4_data")

        mock_file.write.assert_called_once_with(b"fake_mp4_data")
        mock_clip.close.assert_called_once()
        self.assertEqual(sample_rate, 44100)
        self.assertTrue(isinstance(audio_arr, np.ndarray))
        self.assertEqual(audio_arr.shape[0], 2)

    @patch.object(main, "AudioFileClip", side_effect=Exception("Invalid audio format"))
    def test_mp4_audio_to_arr_error_handling(self, mock_audio_clip):
        with self.assertRaises(Exception):
            main.mp4_audio_to_arr(b"invalid_audio_data")


class TestDataValidation(unittest.TestCase):
    def setUp(self):
        main.point = {}

    def create_mock_message(self, topic, payload):
        message = Mock()
        message.topic = topic
        message.payload = json.dumps(payload).encode("utf-8") if isinstance(payload, dict) else payload
        return message

    def test_missing_required_fields_position(self):
        incomplete_pos_data = {
            "lon": 2.17,
            "alt": 100.5,
            "session_uuid": "test-session-123",
            "user_uuid": "test-user-456",
            "type": "GPS",
            "source": "mobile",
            "time": 1234567890,
            "test": "False",
        }

        message = self.create_mock_message("pos", incomplete_pos_data)
        with patch.object(main, "INFLUXDBCLIENT") as mock_influx:
            main.on_message(Mock(), Mock(), message)
            self.assertIn(1234567890, main.point)
            mock_influx.write_points.assert_not_called()

    def test_invalid_json_handling(self):
        message = Mock()
        message.topic = "pos"
        message.payload = b"invalid json data"

        with self.assertRaises(json.JSONDecodeError):
            main.on_message(Mock(), Mock(), message)

    def test_duplicate_timestamps(self):
        pos_data1 = {
            "lat": 41.38,
            "lon": 2.17,
            "alt": 100.5,
            "session_uuid": "session1",
            "user_uuid": "user1",
            "type": "GPS",
            "source": "mobile",
            "time": 1234567890,
            "test": "False",
        }
        pos_data2 = {
            "lat": 41.39,
            "lon": 2.18,
            "alt": 101.0,
            "session_uuid": "session2",
            "user_uuid": "user2",
            "type": "GPS",
            "source": "mobile",
            "time": 1234567890,
            "test": "False",
        }

        message1 = self.create_mock_message("pos", pos_data1)
        message2 = self.create_mock_message("pos", pos_data2)

        with patch.object(main, "INFLUXDBCLIENT") as mock_influx:
            main.on_message(Mock(), Mock(), message1)
            main.on_message(Mock(), Mock(), message2)
            self.assertEqual(main.point[1234567890]["session_uuid"], "session2")
            self.assertEqual(main.point[1234567890]["lat"], 41.39)
            mock_influx.write_points.assert_not_called()


class TestIntegration(unittest.TestCase):
    def setUp(self):
        main.point = {}

    def create_mock_message(self, topic, payload):
        message = Mock()
        message.topic = topic
        message.payload = json.dumps(payload).encode("utf-8") if isinstance(payload, dict) else payload
        return message

    @patch.object(main, "mp4_audio_to_arr")
    def test_full_workflow_multiple_points(self, mock_audio_converter):
        mock_audio_converter.return_value = (np.array([0.1, 0.2, -0.1]), 44100)

        test_points = [
            {"pos": {"lat": 41.38, "lon": 2.17, "alt": 100.5, "time": 1000}, "audio": b"audio1"},
            {"pos": {"lat": 41.39, "lon": 2.18, "alt": 101.0, "time": 2000}, "audio": b"audio2"},
            {"pos": {"lat": 41.40, "lon": 2.19, "alt": 102.0, "time": 3000}, "audio": b"audio3"},
        ]

        for point_data in test_points:
            point_data["pos"].update({
                "session_uuid": "test-session",
                "user_uuid": "test-user",
                "type": "GPS",
                "source": "mobile",
                "test": "False",
            })

        with patch.object(main, "compute_audio_features", return_value={
            "sound": 0.15,
            "sound_db": 46.0,
            "sound_peak": 0.2,
            "sound_rms": 0.15,
            "sound_rms_db": 45.0,
            "sound_variance": 0.02,
            "zero_crossing_rate": 0.5,
            "duration_s": 1.0,
            "spectral_centroid": 500.0,
            "spectral_rolloff": 800.0,
        }), \
             patch.object(main, "classify_audio", return_value=("Traffic", 0.91)), \
             patch.object(main, "INFLUXDBCLIENT") as mock_influx:
            mock_influx.write_points.return_value = True

            for point_data in test_points:
                main.on_message(Mock(), Mock(), self.create_mock_message("pos", point_data["pos"]))
                main.on_message(Mock(), Mock(), self.create_mock_message(str(point_data["pos"]["time"]), point_data["audio"]))

            self.assertEqual(mock_influx.write_points.call_count, 3)
            self.assertEqual(len(main.point), 0)


if __name__ == '__main__':
    unittest.main(verbosity=2)