#!/usr/bin/env python3
"""
Simple MQTT test publisher for Noise Mapper consumer.

This script publishes a `pos` JSON message to topic `pos` and then publishes the binary
MP4 audio file to a topic whose name is the integer timestamp (`time` field).

Usage:
  python scripts/publish_test.py --host localhost --port 1883 --file data/noisy_1667814315_audio_record_v2.mp4

Dependencies:
  pip install paho-mqtt python-dotenv

"""
import argparse
import json
import time
import uuid
import os
from dotenv import load_dotenv
import paho.mqtt.client as mqtt


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default=os.getenv("MQTT_HOST", "localhost"), help="MQTT host")
    parser.add_argument("--port", type=int, default=int(os.getenv("MQTT_PORT", "1883")), help="MQTT port")
    parser.add_argument("--user", default=os.getenv("MQTT_USERNAME", None), help="MQTT username")
    parser.add_argument("--password", default=os.getenv("MQTT_PASSWORD", None), help="MQTT password")
    parser.add_argument("--file", required=True, help="Path to an mp4 audio file to publish")
    parser.add_argument("--lat", type=float, default=13.0827, help="Latitude")
    parser.add_argument("--lon", type=float, default=80.2707, help="Longitude")
    parser.add_argument("--alt", type=float, default=10.0, help="Altitude")
    parser.add_argument("--user_uuid", default="test_user", help="user_uuid to send")
    parser.add_argument("--session_uuid", default=str(uuid.uuid4()), help="session_uuid to send")
    parser.add_argument("--type", default="test", help="location type")
    parser.add_argument("--source", default="script", help="location source")
    parser.add_argument("--test", action="store_true", help="mark as test message")
    args = parser.parse_args()

    # Load .env if present
    load_dotenv()

    if not os.path.isfile(args.file):
        print(f"ERROR: file not found: {args.file}")
        return

    client = mqtt.Client()
    if args.user or args.password:
        client.username_pw_set(args.user, args.password)

    print(f"Connecting to MQTT broker {args.host}:{args.port} ...")
    client.connect(args.host, args.port)
    client.loop_start()

    rx_time = int(time.time())

    pos = {
        "lat": args.lat,
        "lon": args.lon,
        "alt": args.alt,
        "session_uuid": args.session_uuid,
        "user_uuid": args.user_uuid,
        "type": args.type,
        "source": args.source,
        "time": rx_time,
        "test": bool(args.test)
    }

    print(f"Publishing pos to topic 'pos': {pos}")
    client.publish("pos", json.dumps(pos))

    # small pause to let consumer process the pos message
    time.sleep(0.5)

    with open(args.file, "rb") as f:
        data = f.read()

    topic = str(rx_time)
    print(f"Publishing audio file {args.file} to topic '{topic}' (size={len(data)} bytes)")
    client.publish(topic, data)

    # allow some time for delivery
    time.sleep(1.0)
    client.loop_stop()
    client.disconnect()
    print("Done.")


if __name__ == "__main__":
    main()
