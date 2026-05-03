import paho.mqtt.client as mqtt
import json
import time
import os
from dotenv import load_dotenv
import random

load_dotenv()

MQTT_HOST = os.getenv("MQTT_HOST", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_USERNAME = os.getenv("MQTT_USERNAME", "")
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD", "")

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# Get all audio files from data folder
audio_files = [
    "noisy_1667814315_audio_record_v2.mp4",
    "noisy_1667814350_audio_record_v2.mp4",
    "noisy_1667814736_audio_record_v2.mp4",
    "noisy_1667814970_audio_record_v2.mp4",
    "noisy_1667815005_audio_record_v2.mp4",
    "noisy_1667815363_audio_record_v2.mp4",
    "noisy_1667815817_audio_record_v2.mp4",
    "noisy_1667815853_audio_record_v2.mp4",
    "noisy_1667816060_audio_record_v2.mp4",
    "noisy_1667816565_audio_record_v2.mp4",
]

# Create many locations across Tamil Nadu (your area) and other Indian cities
locations = [
    # Tamil Nadu locations (near you)
    {"lat": 11.9295, "lon": 79.7895, "name": "Vellore - City Center"},
    {"lat": 11.9250, "lon": 79.7850, "name": "Vellore - Bus Stand"},
    {"lat": 11.9320, "lon": 79.7920, "name": "Vellore - Railway Station"},
    {"lat": 11.9180, "lon": 79.7950, "name": "Vellore - VIT University"},
    {"lat": 11.9400, "lon": 79.8000, "name": "Vellore - Highway"},
    
    # More Tamil Nadu cities
    {"lat": 13.0827, "lon": 80.2707, "name": "Chennai - Marina Beach"},
    {"lat": 13.0500, "lon": 80.2824, "name": "Chennai - T Nagar"},
    {"lat": 11.0168, "lon": 76.9558, "name": "Coimbatore - RS Puram"},
    {"lat": 10.7905, "lon": 78.7047, "name": "Tiruchirappalli - Junction"},
    {"lat": 9.9252, "lon": 78.1198, "name": "Madurai - Meenakshi Temple"},
    
    # Other major Indian cities
    {"lat": 19.0760, "lon": 72.8777, "name": "Mumbai - Gateway of India"},
    {"lat": 28.6139, "lon": 77.2090, "name": "Delhi - Connaught Place"},
    {"lat": 12.9716, "lon": 77.5946, "name": "Bangalore - MG Road"},
    {"lat": 17.3850, "lon": 78.4867, "name": "Hyderabad - Charminar"},
    {"lat": 22.5726, "lon": 88.3639, "name": "Kolkata - Park Street"},
    
    # More varied locations
    {"lat": 23.0225, "lon": 72.5714, "name": "Ahmedabad - Sabarmati"},
    {"lat": 18.5204, "lon": 73.8567, "name": "Pune - FC Road"},
    {"lat": 26.9124, "lon": 75.7873, "name": "Jaipur - Hawa Mahal"},
    {"lat": 21.1458, "lon": 79.0882, "name": "Nagpur - Sitabuldi"},
    {"lat": 15.2993, "lon": 74.1240, "name": "Goa - Panaji Beach"},
]

def publish_sample(client, location, audio_file, session_uuid, user_uuid):
    """Publish one sample with location and audio"""
    
    timestamp = int(time.time())
    
    # Publish location
    pos_data = {
        "lat": location["lat"],
        "lon": location["lon"],
        "alt": random.uniform(0, 100),
        "session_uuid": session_uuid,
        "user_uuid": user_uuid,
        "type": "gps",
        "source": "demo_data",
        "test": False,
        "time": timestamp
    }
    
    client.publish("pos", json.dumps(pos_data))
    
    # Publish audio
    audio_path = os.path.join(SCRIPT_DIR, "data", audio_file)
    if os.path.exists(audio_path):
        with open(audio_path, "rb") as f:
            audio_data = f.read()
        client.publish(str(timestamp), audio_data)
        return True
    return False

def main():
    print("🚀 Publishing MANY Sample Data Points for Presentation!")
    print(f"📡 Connecting to MQTT broker at {MQTT_HOST}:{MQTT_PORT}\n")
    
    # Connect to MQTT
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1)
    if MQTT_USERNAME:
        client.username_pw_set(username=MQTT_USERNAME, password=MQTT_PASSWORD)
    client.connect(MQTT_HOST, MQTT_PORT)
    client.loop_start()
    
    time.sleep(2)
    
    session_uuid = "presentation-demo-2026"
    user_uuid = "demo-user-india"
    
    total_samples = len(locations)
    print(f"📊 Publishing {total_samples} samples across India...\n")
    print("="*70)
    
    for i, location in enumerate(locations, 1):
        # Pick a random audio file
        audio_file = random.choice(audio_files)
        
        print(f"[{i}/{total_samples}] 📍 {location['name']}")
        print(f"           Coordinates: ({location['lat']:.4f}, {location['lon']:.4f})")
        print(f"           Audio: {audio_file[:30]}...")
        
        success = publish_sample(client, location, audio_file, session_uuid, user_uuid)
        
        if success:
            print(f"           ✅ Published!")
        else:
            print(f"           ⚠️ Audio file not found")
        
        print()
        time.sleep(1)  # Small delay between samples
    
    print("="*70)
    print("\n⏳ Waiting for consumer to process all data...")
    time.sleep(15)
    
    client.loop_stop()
    client.disconnect()
    
    print("\n" + "="*70)
    print(f"✅ Successfully published {total_samples} samples!")
    print("="*70)
    print("\n🗺️  Check your noise map at: http://localhost:5000/noisemap")
    print("📊 Check Grafana dashboard at: http://localhost:3000")
    print("\n🎤 Your presentation data is ready!")
    print(f"\n📍 Map now shows {total_samples} locations across India!")

if __name__ == "__main__":
    main()