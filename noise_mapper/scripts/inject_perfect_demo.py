from influxdb import InfluxDBClient
import time
import random
import uuid

# Connect to the local InfluxDB port
client = InfluxDBClient('localhost', 8086, 'root', 'root', 'noisemapper')

base_lat = 11.9222
base_lon = 79.6278

classes = [
    ("Speech", 0.85, 0.005),
    ("Traffic", 0.92, 0.015),
    ("Music", 0.78, 0.010),
    ("Animal Barking", 0.88, 0.008),
    ("Gunshot", 0.95, 0.025),
    ("Siren", 0.91, 0.020)
]

points = []
current_time_ns = int(time.time() * 1e9)

for i in range(30):
    noise_class, conf, base_sound = random.choice(classes)
    
    lat = base_lat + random.uniform(-0.015, 0.015)
    lon = base_lon + random.uniform(-0.015, 0.015)
    
    sound_val = base_sound + random.uniform(-0.002, 0.005)
    
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
            "sound": sound_val,
            "noise_class": noise_class,
            "confidence": conf + random.uniform(-0.05, 0.04)
        }
    }
    points.append(point)

client.write_points(points)
print(f"SUCCESS! {len(points)} perfect demo points injected into 'samples'.")
