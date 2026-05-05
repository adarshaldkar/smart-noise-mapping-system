import os
import time
import json
import uuid
import requests
import argparse

# The URL of your local Flask API
API_URL = "http://localhost:5000/collect"

# Pre-defined Viva Test Locations in India
LOCATIONS = {
    "Delhi":     {"lat": 28.6139, "lon": 77.2090, "alt": 216.0},
    "Mumbai":    {"lat": 19.0760, "lon": 72.8777, "alt": 14.0},
    "Bangalore": {"lat": 12.9716, "lon": 77.5946, "alt": 920.0},
    "Chennai":   {"lat": 13.0827, "lon": 80.2707, "alt": 6.0},
}

def simulate_event(audio_filepath, city_name):
    """
    Simulates a mobile app sending an audio sample from a specific city.
    """
    if not os.path.exists(audio_filepath):
        print(f"[X] Error: Audio file '{audio_filepath}' not found!")
        return False
        
    if city_name not in LOCATIONS:
        print(f"[X] Error: City '{city_name}' not found in coordinates list!")
        return False

    import random
    coords = LOCATIONS[city_name]
    
    # Add a tiny random jitter so multiple test points don't perfectly overlap
    jitter_lat = random.uniform(-0.01, 0.01)
    jitter_lon = random.uniform(-0.01, 0.01)
    
    timestamp_ms = int(time.time() * 1000)
    
    # Generate fake UUIDs for the simulation
    session_uuid = str(uuid.uuid4())
    user_uuid = str(uuid.uuid4())
    
    metadata = {
        "lat": coords["lat"] + jitter_lat,
        "lon": coords["lon"] + jitter_lon,
        "alt": coords["alt"],
        "session_uuid": session_uuid,
        "user_uuid": user_uuid,
        "user_name": "Viva_Demo_Simulation",
        "type": "new",
        "source": "gnss",
        "test": False,
        "time": timestamp_ms
    }

    print(f"\n[>] Sending Simulation Data...")
    print(f"     City: {city_name}")
    print(f"     File: {os.path.basename(audio_filepath)}")
    print(f"     Time: {timestamp_ms}")

    try:
        with open(audio_filepath, 'rb') as f:
            files = {'audio': (os.path.basename(audio_filepath), f, 'audio/wav')}
            data = {'metadata': json.dumps(metadata)}
            
            response = requests.post(API_URL, data=data, files=files)
            
            if response.status_code == 200:
                print(f"[+] SUCCESS! The sample was sent to the pipeline.")
                return True
            else:
                print(f"[-] FAILED. Server responded with {response.status_code}: {response.text}")
                return False
    except Exception as e:
        print(f"[X] CRASH: Could not connect to API. {e}")
        return False

if __name__ == "__main__":
    print("===================================================")
    print("      NOISE MAPPER: VIVA DEMO SIMULATION SCRIPT    ")
    print("===================================================")
    
    parser = argparse.ArgumentParser(description="Simulate audio events from different cities.")
    parser.add_argument("file", help="Path to the .wav or .mp3 file to send")
    parser.add_argument("city", help=f"City name. Choose from: {', '.join(LOCATIONS.keys())}")
    
    args = parser.parse_args()
    
    simulate_event(args.file, args.city)
    
    print("\n[INFO] Check http://localhost:5000/dashboard in 5 seconds to see the new map point!")
