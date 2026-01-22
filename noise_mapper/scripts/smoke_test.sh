#!/usr/bin/env bash
set -euo pipefail
# Simple smoke test: build, start, publish test message, verify InfluxDB
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "Building images and starting compose (detached)..."
docker compose build --pull

docker compose up -d

echo "Waiting for API to become healthy (up to 60s)..."
for i in {1..12}; do
  cid=$(docker compose ps -q noisemapper_api 2>/dev/null || true)
  status=$(docker inspect --format='{{json .State.Health.Status}}' "$cid" 2>/dev/null || true)
  if [[ "$status" == "\"healthy\"" ]]; then
    echo "API healthy"
    break
  fi
  echo "Waiting... ($i)"
  sleep 5
done

# fallback: continue even if not healthy

# Run publisher
MP4="${ROOT}/data/noisy_1667814315_audio_record_v2.mp4"
if [ ! -f "$MP4" ]; then
  echo "Test audio file not found: $MP4"
  exit 1
fi

echo "Publishing pos JSON and audio file to MQTT broker using mosquitto_pub (dockerized)..."
rx_time=$(date +%s)
POS_JSON=$(cat <<JSON
{"lat":41.38,"lon":2.17,"alt":10.0,"session_uuid":"smoke-session","user_uuid":"smoke-user","type":"test","source":"smoke","time":$rx_time,"test":true}
JSON
)
# Publish pos JSON
echo "$POS_JSON" | docker run --rm -i --network noise_mapper_private eclipse-mosquitto mosquitto_pub -h mosquitto -t pos -s
# small pause
sleep 1
# Publish binary mp4 to topic named by timestamp
cat "$MP4" | docker run --rm -i --network noise_mapper_private eclipse-mosquitto mosquitto_pub -h mosquitto -t "$rx_time" -s

sleep 2

# Query InfluxDB for latest sample
echo "Querying InfluxDB for latest sample..."
RESULT=$(docker exec -it influxdb bash -lc "influx -database noisemapper -execute 'select * from samples order by time desc limit 1'" || true)

if echo "$RESULT" | grep -q "measurement" || echo "$RESULT" | grep -q "samples"; then
  echo "InfluxDB contains sample (smoke test passed)."
  echo "$RESULT"
  exit 0
else
  echo "No sample found in InfluxDB. Output:" >&2
  echo "$RESULT" >&2
  exit 2
fi
echo "Publishing pos JSON and audio file to MQTT broker using mosquitto_pub (dockerized)..."
rx_time=$(date +%s)
POS_JSON=$(cat <<JSON
{"lat":41.38,"lon":2.17,"alt":10.0,"session_uuid":"smoke-session","user_uuid":"smoke-user","type":"test","source":"smoke","time":$rx_time,"test":true}
JSON
)
# Publish pos JSON
echo "$POS_JSON" | docker run --rm -i --network noise_mapper_private eclipse-mosquitto mosquitto_pub -h mosquitto -t pos -s
# small pause
sleep 1
# Publish binary mp4 to topic named by timestamp
cat "$MP4" | docker run --rm -i --network noise_mapper_private eclipse-mosquitto mosquitto_pub -h mosquitto -t "$rx_time" -s
