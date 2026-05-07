"""
Script to insert static test data into InfluxDB for testing Noise Mapper features.
Run with: python insert_test_data.py
"""
from influxdb import InfluxDBClient
import time

client = InfluxDBClient(host='localhost', port=8086)

# Create database if it doesn't exist
client.create_database('noisemapper')
client.switch_database('noisemapper')

print("Connected to InfluxDB, inserting test data...")

# Static test data: 10 points across 2 sessions
# lat/lon around Indian cities, sound values range from quiet (0.003) to loud (0.02)
test_points = [
    # Session 1 - Chennai
    {"measurement": "samples", "tags": {"session_uuid": "session-001", "user_uuid": "test-user", "test": "false", "source": "gnss", "type": "new"}, "time": 1745000000000000000, "fields": {"lat": 13.0827, "lon": 80.2707, "sound": 0.0045, "alt": 12.0}},
    {"measurement": "samples", "tags": {"session_uuid": "session-001", "user_uuid": "test-user", "test": "false", "source": "gnss", "type": "new"}, "time": 1745000060000000000, "fields": {"lat": 13.0832, "lon": 80.2710, "sound": 0.0082, "alt": 11.5}},
    {"measurement": "samples", "tags": {"session_uuid": "session-001", "user_uuid": "test-user", "test": "false", "source": "gnss", "type": "new"}, "time": 1745000120000000000, "fields": {"lat": 13.0838, "lon": 80.2715, "sound": 0.0153, "alt": 10.0}},
    {"measurement": "samples", "tags": {"session_uuid": "session-001", "user_uuid": "test-user", "test": "false", "source": "gnss", "type": "new"}, "time": 1745000180000000000, "fields": {"lat": 13.0844, "lon": 80.2720, "sound": 0.0190, "alt":  9.0}},
    {"measurement": "samples", "tags": {"session_uuid": "session-001", "user_uuid": "test-user", "test": "false", "source": "gnss", "type": "new"}, "time": 1745000240000000000, "fields": {"lat": 13.0850, "lon": 80.2724, "sound": 0.0200, "alt":  8.5}},
    # Session 2 - Mumbai
    {"measurement": "samples", "tags": {"session_uuid": "session-002", "user_uuid": "test-user", "test": "false", "source": "gnss", "type": "new"}, "time": 1745003600000000000, "fields": {"lat": 19.0760, "lon": 72.8777, "sound": 0.0031, "alt": 13.0}},
    {"measurement": "samples", "tags": {"session_uuid": "session-002", "user_uuid": "test-user", "test": "false", "source": "gnss", "type": "new"}, "time": 1745003660000000000, "fields": {"lat": 19.0765, "lon": 72.8782, "sound": 0.0064, "alt": 12.5}},
    {"measurement": "samples", "tags": {"session_uuid": "session-002", "user_uuid": "test-user", "test": "false", "source": "gnss", "type": "new"}, "time": 1745003720000000000, "fields": {"lat": 19.0772, "lon": 72.8788, "sound": 0.0120, "alt": 11.0}},
    {"measurement": "samples", "tags": {"session_uuid": "session-002", "user_uuid": "test-user", "test": "false", "source": "gnss", "type": "new"}, "time": 1745003780000000000, "fields": {"lat": 19.0785, "lon": 72.8800, "sound": 0.0050, "alt":  9.5}},
    {"measurement": "samples", "tags": {"session_uuid": "session-002", "user_uuid": "test-user", "test": "false", "source": "gnss", "type": "new"}, "time": 1745003840000000000, "fields": {"lat": 19.0800, "lon": 72.8820, "sound": 0.0098, "alt": 10.5}},
    # A few API metrics too (to test Grafana)
    {"measurement": "metrics", "tags": {}, "time": 1745000000000000000, "fields": {"api_response_time": 0.12}},
    {"measurement": "metrics", "tags": {}, "time": 1745003600000000000, "fields": {"api_response_time": 0.09}},
]

result = client.write_points(test_points)
print(f"Write result: {result}")

# Verify
res = list(client.query("SELECT COUNT(*) FROM samples"))
print(f"Total samples in DB: {res[0][0] if res else 0}")

res2 = list(client.query("SELECT * FROM samples ORDER BY time DESC LIMIT 3"))
if res2:
    for row in res2[0]:
        print(f"  lat={row['lat']:.4f}, lon={row['lon']:.4f}, sound={row['sound']:.4f}")

print("\nDone! Visit http://localhost:5000/noisemap to see the noise map.")
