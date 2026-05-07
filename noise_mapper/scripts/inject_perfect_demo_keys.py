from influxdb import InfluxDBClient
import time
import random
import uuid

# Connect to the local InfluxDB
client = InfluxDBClient('localhost', 8086, 'root', 'root', 'noisemapper')

# Clean out the bad demo data I just injected so it doesn't crowd the map with 0s
client.query("DELETE FROM samples WHERE user_uuid='demo-user'")
print("Cleared old demo points.")

base_lat = 11.9222
base_lon = 79.6278

classes = [
    ("Speech", 0.85, 45.0, 0.4, 0.05, 1200),
    ("Traffic", 0.92, 72.0, 0.8, 0.15, 2500),
    ("Music", 0.78, 65.0, 0.6, 0.08, 3000),
    ("Animal Barking", 0.88, 58.0, 0.7, 0.04, 1800),
    ("Gunshot", 0.95, 95.0, 1.0, 0.20, 4000),
    ("Siren", 0.91, 88.0, 0.9, 0.10, 3500)
]

points = []
current_time_ns = int(time.time() * 1e9)

for i in range(30):
    noise_class, conf, base_db, peak, zcr, centroid = random.choice(classes)
    
    lat = base_lat + random.uniform(-0.015, 0.015)
    lon = base_lon + random.uniform(-0.015, 0.015)
    
    sound_db = base_db + random.uniform(-5.0, 5.0)
    
    point = {
        "measurement": "samples",
        "tags": {
            "session_uuid": str(uuid.uuid4()),
            "user_uuid": "demo-user",
            "test": "False",
            "source": "gnss",
            "type": "new"
        },
        "time": current_time_ns - (i * 10 * 1000000000), 
        "fields": {
            "lat": lat,
            "lon": lon,
            "alt": 10.0,
            "sound_db": sound_db,
            "sound_peak": peak + random.uniform(-0.1, 0.0),
            "sound_rms": (sound_db / 100.0) * random.uniform(0.8, 1.2),  # Mock RMS relative to dB
            "zero_crossing_rate": zcr + random.uniform(-0.01, 0.01),
            "spectral_centroid": centroid + random.uniform(-200, 200),
            "spectral_rolloff": centroid * 1.5,
            "duration_s": random.uniform(2.5, 4.0),
            "noise_class": noise_class,
            "confidence": conf + random.uniform(-0.05, 0.04),
            "user_name": "Demo Admin",
            "audio_filename": "presentation_audio.wav"
        }
    }
    points.append(point)

client.write_points(points)
print(f"SUCCESS! {len(points)} perfect demo points injected into 'samples' with correct keys.")
