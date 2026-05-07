import paho.mqtt.client as mqtt
from paho.mqtt.enums import CallbackAPIVersion
from influxdb import InfluxDBClient
import json
from moviepy.editor import AudioFileClip  # type: ignore[import-not-found]
import numpy as np
import tempfile
import os
from dotenv import load_dotenv
import uuid
from ml_classifier import classify_audio
import logging
import librosa

logging.basicConfig(format="%(asctime)s %(levelname)-8s %(message)s",
                    level=logging.INFO,
                    datefmt="%Y-%m-%d %H:%M:%S")

load_dotenv()

INFLUX_PORT = 8086
INFLUX_DATABASE = "noisemapper"
if os.environ.get('AM_I_IN_A_DOCKER_CONTAINER', False):
    INFLUX_HOST = "influxdb"
else:
    INFLUX_HOST = "localhost"

MQTT_HOST = os.getenv("MQTT_HOST", "mosquitto" if os.environ.get('AM_I_IN_A_DOCKER_CONTAINER', False) else "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_USERNAME = os.getenv("MQTT_USERNAME", "")
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD", "")

INFLUXDBCLIENT = InfluxDBClient(host=INFLUX_HOST, port=INFLUX_PORT)
try:
    INFLUXDBCLIENT.create_database(INFLUX_DATABASE)
    INFLUXDBCLIENT.switch_database(INFLUX_DATABASE)
    logging.info(f"Connected to InfluxDB at {INFLUX_HOST}:{INFLUX_PORT}, database '{INFLUX_DATABASE}' is ready.")
except Exception as e:
    logging.error(f"Could not initialize InfluxDB: {e}")

point = {}

# All keys required from BOTH pos + audio messages before writing to InfluxDB
# Note: audio features like 'sound', 'sound_rms' etc. are added by compute_audio_features()
REQUIRED_KEYS = {"lat", "lon", "session_uuid", "user_uuid", "type", "source", "test", "noise_class"}


def compute_audio_features(audio_arr, sample_rate):
    """
    Computes a rich set of audio analytics features from a raw audio array.
    All features are stored in InfluxDB and visualized in the Grafana dashboard.

    Returns a dict with all computed fields.
    """
    features = {}
    abs_arr = np.abs(audio_arr)
    audio_f32 = audio_arr.astype(np.float32)

    # --- Amplitude ---
    mean_amp = float(np.mean(abs_arr))
    features["sound"] = mean_amp                                        # raw mean amplitude (backward compat)
    # Calibrated dB: Add 100 to map relative digital dB (-60 to 0) to realistic environmental dB (40 to 100)
    features["sound_db"] = float(20 * np.log10(max(mean_amp, 1e-9)) + 100)
    features["sound_peak"] = float(np.max(abs_arr))                     # peak amplitude (detects spikes)

    # --- RMS Energy (better loudness measure than mean amplitude) ---
    rms = float(np.sqrt(np.mean(audio_arr ** 2)))
    features["sound_rms"] = rms
    features["sound_rms_db"] = float(20 * np.log10(max(rms, 1e-9)) + 100)    # RMS in dB

    # --- Variability ---
    features["sound_variance"] = float(np.var(audio_arr))              # low=steady hum, high=erratic noise

    # --- Zero Crossing Rate ---
    # High ZCR = high-frequency content (speech, hiss)
    # Low  ZCR = low-frequency content (traffic rumble)
    zero_crossings = int(np.sum(np.diff(np.sign(audio_arr)) != 0))
    features["zero_crossing_rate"] = float(zero_crossings / max(len(audio_arr), 1))

    # --- Duration ---
    features["duration_s"] = float(len(audio_arr) / max(sample_rate, 1))

    # --- Spectral Features (via librosa) ---
    try:
        # Spectral Centroid — "brightness": high=sharp/alarm, low=deep rumble
        centroid = librosa.feature.spectral_centroid(y=audio_f32, sr=sample_rate)
        features["spectral_centroid"] = float(np.mean(centroid))

        # Spectral Rolloff — frequency below which 85% of energy lies
        # Separates speech (<4kHz) from broadband noise (>4kHz)
        rolloff = librosa.feature.spectral_rolloff(y=audio_f32, sr=sample_rate, roll_percent=0.85)
        features["spectral_rolloff"] = float(np.mean(rolloff))

    except Exception as e:
        logging.warning(f"Spectral feature extraction failed: {e}")
        features["spectral_centroid"] = 0.0
        features["spectral_rolloff"] = 0.0

    return features


def mp4_audio_to_arr(mp4_audio):
    filename = str(uuid.uuid4())
    with open(f"{filename}.mp4", "wb") as f:
        f.write(mp4_audio)

    try:
        clip = AudioFileClip(f"{filename}.mp4")
        sample_rate = clip.fps
        audio_array = clip.to_soundarray()
        clip.close()
        os.remove(f"{filename}.mp4")

        # Convert to mono if stereo
        if len(audio_array.shape) > 1:
            audio_array = np.mean(audio_array, axis=1)

        return audio_array, sample_rate

    except Exception as e:
        if os.path.exists(f"{filename}.mp4"):
            os.remove(f"{filename}.mp4")
        raise e


def on_message(client, userdata, message):
    global point
    logging.info("Received message")

    if message.topic == "pos":
        logging.info(f"Message received: {str(message.payload.decode('utf-8'))}")
        data = json.loads(message.payload)

        rx_time = data.get("time", None)
        if point.get(rx_time, None) is None:
            point[rx_time] = {}

        point[rx_time]["lat"] = data.get("lat", None)
        point[rx_time]["lon"] = data.get("lon", None)
        point[rx_time]["alt"] = data.get("alt", None)
        point[rx_time]["session_uuid"] = data.get("session_uuid", None)
        point[rx_time]["user_uuid"] = data.get("user_uuid", None)
        point[rx_time]["type"] = data.get("type", None)
        point[rx_time]["source"] = data.get("source", None)
        point[rx_time]["test"] = data.get("test", None)
        point[rx_time]["user_name"] = data.get("user_name", "Anonymous")
        point[rx_time]["audio_filename"] = data.get("audio_filename", "")

    else:
        rx_time = int(message.topic)
        logging.info(f"Received audio file in topic {message.topic}")

        try:
            audio_arr, sample_rate = mp4_audio_to_arr(message.payload)
        except Exception as e:
            logging.error(f"Failed to do mp4 to audio arr, {e}")
            if rx_time in point:
                del point[rx_time]
            return

        if point.get(rx_time, None) is None:
            point[rx_time] = {}

        # Compute all 9 audio analytics features
        logging.info("Computing audio features...")
        features = compute_audio_features(audio_arr, sample_rate)
        point[rx_time].update(features)
        logging.info(
            f"Audio features: rms_db={features['sound_rms_db']:.2f}dB | "
            f"peak={features['sound_peak']:.4f} | "
            f"zcr={features['zero_crossing_rate']:.4f} | "
            f"centroid={features['spectral_centroid']:.1f}Hz | "
            f"rolloff={features['spectral_rolloff']:.1f}Hz | "
            f"duration={features['duration_s']:.2f}s"
        )

        # ML Classification — What type of sound is this?
        ml_class, conf = classify_audio(audio_arr, original_sr=sample_rate)
        if ml_class is not None:
            point[rx_time]["noise_class"] = ml_class
            point[rx_time]["confidence"] = conf
        else:
            point[rx_time]["noise_class"] = "unclassified"
            point[rx_time]["confidence"] = 0.0

    # Write to InfluxDB when we have all required fields from both pos + audio messages
    if REQUIRED_KEYS.issubset(point[rx_time].keys()):
        session_uuid = point[rx_time].pop("session_uuid")
        user_uuid = point[rx_time].pop("user_uuid")
        location_type = point[rx_time].pop("type")
        location_source = point[rx_time].pop("source")
        test = point[rx_time].pop("test")
        
        # Pull noise_class out to use as a TAG for better indexing and dashboard consistency
        noise_class = point[rx_time].pop("noise_class", "unclassified")

        try:
            point_fields = dict(point[rx_time])
            point_fields["noise_class"] = noise_class
            # rx_time is in milliseconds from the Flutter app.
            # Pass it directly with time_precision='ms' to avoid int64 overflow.
            point_out = {
                "measurement": "samples",
                "fields": point_fields,
                "time": int(rx_time)  # milliseconds
            }
            ret = INFLUXDBCLIENT.write_points(
                [point_out],
                time_precision='ms',  # <-- tell InfluxDB the timestamp is in ms
                tags={
                    "session_uuid": session_uuid,
                    "user_uuid": user_uuid,
                    "type": location_type,
                    "source": location_source,
                    "test": str(test),
                    "noise_class_tag": noise_class
                }
            )
            logging.info(f"Point inserted in influx (Class: {noise_class}). ret={ret}.")
            del point[rx_time]
        except Exception as e:
            logging.error(f"Error writing point: {e}")


if __name__ == "__main__":
    client = mqtt.Client(callback_api_version=CallbackAPIVersion.VERSION1)
    client.on_message = on_message
    if MQTT_USERNAME or MQTT_PASSWORD:
        client.username_pw_set(username=MQTT_USERNAME, password=MQTT_PASSWORD)
    client.connect(MQTT_HOST)
    logging.info("Broker connection established")
    client.subscribe("#")
    client.on_message = on_message
    client.loop_forever()
