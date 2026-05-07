import paho.mqtt.client as mqtt
import json
import time
import os
from dotenv import load_dotenv

load_dotenv()

MQTT_HOST = os.getenv("MQTT_HOST", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_USERNAME = os.getenv("MQTT_USERNAME", "")
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD", "")

# Get the directory where this script is located
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# Sample locations in India using REAL audio files from your data folder
locations = [
    {"lat": 13.0827, "lon": 80.2707, "file": os.path.join(SCRIPT_DIR, "data", "noisy_1667814315_audio_record_v2.mp4"), "name": "Chennai - Marina Beach"},
    {"lat": 19.0760, "lon": 72.8777, "file": os.path.join(SCRIPT_DIR, "data", "noisy_1667815853_audio_record_v2.mp4"), "name": "Mumbai - Gateway of India"},
    {"lat": 28.6139, "lon": 77.2090, "file": os.path.join(SCRIPT_DIR, "data", "noisy_1667816060_audio_record_v2.mp4"), "name": "Delhi - Connaught Place"},
    {"lat": 12.9716, "lon": 77.5946, "file": os.path.join(SCRIPT_DIR, "data", "noisy_1667815817_audio_record_v2.mp4"), "name": "Bengaluru - MG Road"},
    {"lat": 22.5726, "lon": 88.3639, "file": os.path.join(SCRIPT_DIR, "data", "noisy_1667814736_audio_record_v2.mp4"), "name": "Kolkata - Park Street"},
]

def publish_audio_sample(client, location, session_uuid, user_uuid):
    """Publish audio sample just like the Android app does"""
    
    timestamp = int(time.time())
    
    # Step 1: Publish location data
    pos_data = {
        "lat": location["lat"],
        "lon": location["lon"],
        "alt": 10.0,
        "session_uuid": session_uuid,
        "user_uuid": user_uuid,
        "type": "gps",
        "source": "sample_data",
        "test": False,
        "time": timestamp
    }
    
    client.publish("pos", json.dumps(pos_data))
    print(f"📍 Published location: {location['name']} ({location['lat']}, {location['lon']})")
    
    # Step 2: Publish audio file
    if not os.path.exists(location["file"]):
        print(f"❌ ERROR: File not found: {location['file']}")
        return None
        
    with open(location["file"], "rb") as f:
        audio_data = f.read()
    
    client.publish(str(timestamp), audio_data)
    print(f"🎵 Published audio from {os.path.basename(location['file'])} ({len(audio_data)} bytes)")
    
    return timestamp


def main():
    print("🚀 Starting Sample Data Publisher...")
    print(f"📡 Connecting to MQTT broker at {MQTT_HOST}:{MQTT_PORT}")
    
    # Connect to MQTT broker
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1)
    if MQTT_USERNAME:
        client.username_pw_set(username=MQTT_USERNAME, password=MQTT_PASSWORD)
    client.connect(MQTT_HOST, MQTT_PORT)
    client.loop_start()
    
    time.sleep(2)  # Wait for connection
    
    session_uuid = "sample-session-india"
    user_uuid = "demo-user-india"
    
    print("\n" + "="*60)
    print(f"📊 Publishing {len(locations)} Real Audio Samples from India...")
    print("="*60 + "\n")
    
    # Publish each sample
    for i, location in enumerate(locations, 1):
        print(f"\n[{i}/{len(locations)}] Processing: {location['name']}")
        print(f"🔍 File: {os.path.basename(location['file'])}")
        timestamp = publish_audio_sample(client, location, session_uuid, user_uuid)
        if timestamp:
            print(f"✅ Completed! Timestamp: {timestamp}")
        else:
            print(f"⚠️ Skipped due to error")
        
        # Wait a bit between samples to allow processing
        if i < len(locations):
            print("\n⏳ Waiting 3 seconds before next sample...\n")
            time.sleep(3)
    
    # Keep connection alive to ensure all messages are delivered
    print("\n⏳ Waiting for consumer to process all audio data...")
    time.sleep(15)
    
    client.loop_stop()
    client.disconnect()
    
    print("\n" + "="*60)
    print(f"✅ All {len(locations)} samples published successfully!")
    print("="*60)
    print("\n📍 Check your noise map at: http://localhost:5000/noisemap")
    print("📊 Check Grafana dashboard at: http://localhost:3000")
    print("\n🎵 Real Indian audio recordings are now being analyzed!")


if __name__ == "__main__":
    main()