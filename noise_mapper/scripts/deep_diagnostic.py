import requests
import json
import socket
from influxdb import InfluxDBClient
import urllib.request
import os

print("========================================")
print("NOISE MAPPER DEEP DIAGNOSTIC SUITE")
print("========================================\n")

issues = []

# 1. Check Flask API HTTP Endpoints
print("[*] Checking Flask API Endpoints...")
try:
    res = requests.get('http://localhost:5000/dashboard', timeout=2)
    if res.status_code == 200:
        print("  [PASS] /dashboard is reachable")
    else:
        issues.append(f"/dashboard returned {res.status_code}")
except Exception as e:
    issues.append(f"Flask API unreachable: {e}")

try:
    res = requests.get('http://localhost:5000/api/stats', timeout=2)
    if res.status_code == 200:
        print("  [PASS] /api/stats is functioning")
    else:
        issues.append(f"/api/stats failed")
except Exception as e:
    issues.append(f"/api/stats failed: {e}")

# 2. Check MQTT Broker (Mosquitto)
print("[*] Checking MQTT Broker (Mosquitto)...")
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.settimeout(2)
try:
    s.connect(('localhost', 1883))
    print("  [PASS] Mosquitto is running on port 1883")
    s.close()
except Exception as e:
    issues.append(f"MQTT Broker unreachable: {e}")

# 3. Check InfluxDB Connection & Schemas
print("[*] Checking InfluxDB & Schemas...")
try:
    client = InfluxDBClient('localhost', 8086, 'root', 'root', 'noisemapper')
    client.ping()
    print("  [PASS] InfluxDB is reachable on port 8086")
    
    measurements = client.get_list_measurements()
    m_names = [m['name'] for m in measurements]
    if 'samples' in m_names:
        print("  [PASS] 'samples' measurement exists")
    else:
        issues.append("'samples' measurement missing from InfluxDB")
except Exception as e:
    issues.append(f"InfluxDB error: {e}")

# 4. Check Grafana
print("[*] Checking Grafana Dashboard...")
try:
    res = requests.get('http://localhost:3000/api/health', timeout=2)
    if res.status_code == 200:
        print("  [PASS] Grafana is running and healthy")
    else:
        issues.append(f"Grafana returned {res.status_code}")
except Exception as e:
    issues.append(f"Grafana unreachable: {e}")

print("\n========================================")
if len(issues) == 0:
    print("RESULT: ALL SYSTEMS GO. ZERO ISSUES DETECTED.")
else:
    print(f"RESULT: {len(issues)} ISSUES DETECTED.")
    for issue in issues:
        print(f" - {issue}")
