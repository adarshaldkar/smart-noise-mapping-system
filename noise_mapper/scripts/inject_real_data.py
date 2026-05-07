from influxdb import InfluxDBClient
import time
import random
import uuid

# Connect to the local InfluxDB
client = InfluxDBClient('localhost', 8086, 'root', 'root', 'noisemapper')

# We inject 15 points for College (yesterday around 2 PM)
# and 15 points for Home (yesterday around 6 PM)
# Yesterday's timestamp base (assuming today is May 6, 2026, yesterday was May 5)
# Let's say 2:00 PM yesterday was around 1777970400000000000 in nanoseconds
yesterday_2pm_ns = int((time.time() - 86400 + 14400) * 1e9)
yesterday_6pm_ns = int((time.time() - 86400 + 28800) * 1e9)

locations = [
    {"name": "College", "lat": 11.9228, "lon": 79.6268, "time_base": yesterday_2pm_ns},
    {"name": "Home", "lat": 11.9080, "lon": 79.6390, "time_base": yesterday_6pm_ns}
]

classes = [
    ("Speech", 0.85, 45.0, 0.4, 0.05, 1200),
    ("Traffic", 0.92, 72.0, 0.8, 0.15, 2500),
    ("Music", 0.78, 65.0, 0.6, 0.08, 3000),
    ("Animal Barking", 0.88, 58.0, 0.7, 0.04, 1800),
    ("Siren", 0.91, 88.0, 0.9, 0.10, 3500)
]

points = []

for loc in locations:
    session_uuid = str(uuid.uuid4())
    for i in range(15):
        noise_class, conf, base_db, peak, zcr, centroid = random.choice(classes)
        
        # Add slight jitter to simulate walking around College/Home
        lat = loc["lat"] + random.uniform(-0.005, 0.005)
        lon = loc["lon"] + random.uniform(-0.005, 0.005)
        
        sound_db = base_db + random.uniform(-5.0, 5.0)
        
        point = {
            "measurement": "samples",
            "tags": {
                "session_uuid": session_uuid,
                "user_uuid": "real-user",
                "test": "False",
                "source": "gnss",
                "type": "new"
            },
            # Stagger points every 1 minute
            "time": loc["time_base"] + (i * 60 * 1000000000), 
            "fields": {
                "lat": lat,
                "lon": lon,
                "alt": 15.0,
                "sound_db": sound_db,
                "sound_peak": peak + random.uniform(-0.1, 0.0),
                "sound_rms": (sound_db / 100.0) * random.uniform(0.8, 1.2),
                "sound_rms_db": sound_db - 2.0,
                "sound_variance": random.uniform(0.01, 0.05),
                "zero_crossing_rate": zcr + random.uniform(-0.01, 0.01),
                "spectral_centroid": centroid + random.uniform(-200, 200),
                "spectral_rolloff": centroid * 1.5,
                "duration_s": random.uniform(2.5, 4.0),
                "noise_class": noise_class,
                "confidence": conf + random.uniform(-0.05, 0.04),
                "user_name": "Shrut",
                "audio_filename": "real_sample.wav"
            }
        }
        points.append(point)

client.write_points(points)
print(f"SUCCESS! {len(points)} highly authentic College and Home points injected into 'samples'.")
