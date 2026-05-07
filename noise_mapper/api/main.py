from influxdb import InfluxDBClient
from datetime import datetime
from typing import Any, Dict, Iterable, List, cast
import folium
from folium.plugins import HeatMap
import numpy as np
import scipy.signal
import branca
import flask
from matplotlib.colors import LinearSegmentedColormap
import logging
import os
import json
import time
import paho.mqtt.publish as publish
import uuid
import requests

# Configure Gemini
api_key = os.environ.get("GEMINI_API_KEY")

logging.basicConfig(format="%(asctime)s %(levelname)-8s %(message)s",
                    level=logging.INFO,
                    datefmt="%Y-%m-%d %H:%M:%S")

CMAP = LinearSegmentedColormap.from_list('rg', ["g", "y", "r"], N=256)

ZOOM_LEVEL_START = 17

INFLUX_PORT = 8086
INFLUX_DATABASE = "noisemapper"
if os.environ.get('AM_I_IN_A_DOCKER_CONTAINER', False):
    INFLUX_HOST = "influxdb"
else:
    INFLUX_HOST = "localhost"

INFLUXDBCLIENT = InfluxDBClient(host=INFLUX_HOST, port=INFLUX_PORT, database=INFLUX_DATABASE)
try:
    INFLUXDBCLIENT.create_database(INFLUX_DATABASE)
    INFLUXDBCLIENT.switch_database(INFLUX_DATABASE)
except Exception as exc:
    logging.warning(f"InfluxDB initialization warning: {exc}")

app = flask.Flask(__name__)

SAMPLE_MEASUREMENT = "samples"

INDIAN_DEMO_CITIES = [
    (13.0827, 80.2707, "Chennai"),
    (19.0760, 72.8777, "Mumbai"),
    (28.6139, 77.2090, "Delhi"),
    (22.5726, 88.3639, "Kolkata"),
    (12.9716, 77.5946, "Bengaluru"),
    (17.3850, 78.4867, "Hyderabad"),
    (11.0168, 76.9558, "Coimbatore"),
    (9.9312, 76.2673, "Kochi"),
]

INDIA_LAT_MIN = 6.0
INDIA_LAT_MAX = 38.0
INDIA_LON_MIN = 68.0
INDIA_LON_MAX = 98.0

INDIA_DEMO_SEEDED = False

def measurements_list_to_field_value(measurements, field_key):
    ret = []
    for measurement in measurements:
        ret.append(measurement.get(field_key, None))
    return ret


def query_points(query: str) -> List[Dict[str, Any]]:
    result = INFLUXDBCLIENT.query(query)
    if isinstance(result, list):
        points: List[Dict[str, Any]] = []
        for result_set in result:
            get_points = getattr(result_set, "get_points", None)
            if callable(get_points):
                points.extend(list(cast(Iterable[Any], get_points())))
        return points

    get_points = getattr(result, "get_points", None)
    if callable(get_points):
        return list(cast(Iterable[Any], get_points()))
    return []


def to_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def is_test_sample(sample: Dict[str, Any]) -> bool:
    value = sample.get("test")
    return str(value).strip().lower() in {"true", "1", "yes"}


def live_samples_only(samples: List[Dict[str, Any]], include_test: bool = False) -> List[Dict[str, Any]]:
    if include_test:
        return samples
    return [sample for sample in samples if not is_test_sample(sample)]


def is_india_sample(sample: Dict[str, Any]) -> bool:
    try:
        lat = float(sample.get("lat"))
        lon = float(sample.get("lon"))
    except (TypeError, ValueError):
        return False
    return INDIA_LAT_MIN <= lat <= INDIA_LAT_MAX and INDIA_LON_MIN <= lon <= INDIA_LON_MAX


def display_noise_class(sample: Dict[str, Any]) -> str:
    for key in ("noise_class", "noise_class_tag", "noise_class_1", "classification", "predicted_class", "ml_class"):
        value = sample.get(key)
        if value not in (None, "", "None", "null"):
            return str(value)
    return "Unknown"


def normalize_sample_record(sample: Dict[str, Any]) -> Dict[str, Any]:
    normalized: Dict[str, Any] = {}
    if "tags" in sample and isinstance(sample.get("tags"), dict):
        normalized.update(sample["tags"])
    if "fields" in sample and isinstance(sample.get("fields"), dict):
        normalized.update(sample["fields"])
    normalized.update({k: v for k, v in sample.items() if k not in {"tags", "fields"}})
    normalized["noise_class"] = display_noise_class(normalized)
    return normalized


def build_indian_demo_points(count: int = 8) -> List[Dict[str, Any]]:
    points: List[Dict[str, Any]] = []
    noise_types = ["Traffic", "Siren", "Speech", "Music", "Animal", "Silence", "Gunshot"]
    for index in range(count):
        city_lat, city_lon, city_name = INDIAN_DEMO_CITIES[index % len(INDIAN_DEMO_CITIES)]
        nt = np.random.choice(noise_types)
        points.append({
            "measurement": SAMPLE_MEASUREMENT,
            "tags": {
                "session_uuid": f"demo-india-{uuid.uuid4().hex[:8]}",
                "noise_class_tag": nt,
                "test": "False",
                "city": city_name,
            },
            "fields": {
                "lat": float(city_lat + (np.random.random() - 0.5) * 0.03),
                "lon": float(city_lon + (np.random.random() - 0.5) * 0.03),
                "sound_db": float(55 + np.random.random() * 20),
                "confidence": float(0.88 + np.random.random() * 0.08),
                "spectral_centroid": float(500 + np.random.random() * 2000),
                "zero_crossing_rate": float(0.01 + np.random.random() * 0.1),
                "user_name": f"Demo Bot ({city_name})",
            },
            "time": datetime.utcnow().isoformat(),
        })
    return points


def seed_indian_demo_points(count: int = 8) -> List[Dict[str, Any]]:
    global INDIA_DEMO_SEEDED
    demo_points = build_indian_demo_points(count)
    if INDIA_DEMO_SEEDED:
        return demo_points

    try:
        INFLUXDBCLIENT.write_points(demo_points)
        INDIA_DEMO_SEEDED = True
    except Exception as exc:
        logging.warning(f"Could not seed Indian demo points: {exc}")
    return demo_points


def preferred_dashboard_samples(samples: List[Dict[str, Any]], include_test: bool = False, seed_count: int = 8) -> List[Dict[str, Any]]:
    india_all   = [s for s in samples if is_india_sample(s)]
    india_real  = [s for s in india_all if not is_test_sample(s)]
    india_demo  = [s for s in india_all if is_test_sample(s)]

    if include_test:
        # Show BOTH real + demo together so Demo Data button is always visible
        return india_real + india_demo

    # Default: only real data; if none, show demo as fallback
    return india_real if india_real else india_demo


def query_preferred_dashboard_samples(query: str, include_test: bool = False, seed_count: int = 8) -> List[Dict[str, Any]]:
    return preferred_dashboard_samples(query_points(query), include_test=include_test, seed_count=seed_count)


def get_db_value(s):
    """Helper to find the best dB field across different versions of the schema."""
    sound = s.get("sound")
    if sound is not None:
        try:
            return float(20 * np.log10(max(to_float(sound, 1e-9), 1e-9)) + 100)
        except Exception:
            pass
    for key in ["sound_db", "sound_rms_db", "rms_db"]:
        val = s.get(key)
        if val is not None:
            numeric_val = to_float(val)
            return numeric_val + 100 if numeric_val < 0 else numeric_val
    return 0

@app.route('/')
def index():
    return flask.render_template('./index.html')

@app.route('/noisemap')
def noisemap():
    try:
        samples = query_preferred_dashboard_samples(f"SELECT * FROM {SAMPLE_MEASUREMENT};")
        if not samples:
            default_coords = (11.9228, 79.6268)
            m = folium.Map(location=default_coords, zoom_start=ZOOM_LEVEL_START)
            folium.Marker(
                default_coords,
                popup="<b>No data yet!</b><br>Start the app to collect noise samples.",
                icon=folium.Icon(color='blue', icon='info-sign')
            ).add_to(m)
            return m._repr_html_()

        lats = measurements_list_to_field_value(samples, "lat")
        lons = measurements_list_to_field_value(samples, "lon")
        
        valid = []
        for i, s in enumerate(samples):
            la, lo = lats[i], lons[i]
            if la is not None and lo is not None:
                valid.append((float(la), float(lo), get_db_value(s), s))

        if not valid:
            default_coords = (11.9228, 79.6268)
            m = folium.Map(location=default_coords, zoom_start=12)
            folium.Marker(default_coords, popup="<b>No valid data yet!</b>", icon=folium.Icon(color='blue', icon='info-sign')).add_to(m)
            return m._repr_html_()

        lats_v = [v[0] for v in valid]
        lons_v = [v[1] for v in valid]
        center = (float(np.mean(lats_v)), float(np.mean(lons_v)))
        m = folium.Map(location=center, zoom_start=15, tiles="OpenStreetMap")
        
        for la, lo, db_val, s_data in valid:
            if db_val > 85: color = "red"
            elif db_val > 65: color = "orange"
            elif db_val > 45: color = "yellow"
            else: color = "green"

            nc = s_data.get("noise_class")
            conf = s_data.get("confidence") or 0
            display_conf = conf * 100 if conf <= 1.0 else conf
            noise_label = nc if (nc and nc not in ("None", "null")) else "Unknown"
            tooltip_text = f"{noise_label} | {round(db_val, 1)} dB | {round(display_conf, 1)}% Conf"

            folium.CircleMarker(
                location=[la, lo],
                radius=8,
                color=color,
                fill=True,
                fill_color=color,
                fill_opacity=0.7,
                tooltip=tooltip_text
            ).add_to(m)

        return m._repr_html_()
    except Exception as e:
        logging.error(f"Error in noisemap: {e}")
        return f"<h1>Error</h1><p>{str(e)}</p>"

@app.route('/collect', methods=['POST'])
def collect():
    try:
        metadata_str = flask.request.form.get('metadata')
        if not metadata_str: return flask.jsonify({"error": "No metadata provided"}), 400
        metadata = json.loads(metadata_str)
        if 'audio' not in flask.request.files: return flask.jsonify({"error": "No audio file provided"}), 400
        audio_file = flask.request.files['audio']
        audio_bytes = audio_file.read()
        audio_dir = os.path.join(app.root_path, 'static', 'audio')
        os.makedirs(audio_dir, exist_ok=True)
        _, audio_ext = os.path.splitext(audio_file.filename or "")
        audio_ext = audio_ext.lower() if audio_ext.lower() in {".mp4", ".m4a", ".aac", ".wav", ".ogg"} else ".m4a"
        filename = f"{metadata.get('session_uuid', 'unknown')}_{metadata.get('time', int(time.time()))}{audio_ext}"
        filepath = os.path.join(audio_dir, filename)
        with open(filepath, 'wb') as f: f.write(audio_bytes)
        metadata["audio_filename"] = filename
        broker_host = "mosquitto"
        msgs: List[Dict[str, Any]] = [
            {"topic": "pos", "payload": json.dumps(metadata), "qos": 0, "retain": False},
            {"topic": str(metadata["time"]), "payload": audio_bytes, "qos": 0, "retain": False}
        ]
        publish.multiple(cast(Any, msgs), hostname=broker_host, port=1883)
        return flask.jsonify({"status": "success", "message": "Data forwarded to ML pipeline"}), 200
    except Exception as e:
        logging.error(f"Error in /collect endpoint: {e}")
        return flask.jsonify({"error": str(e)}), 500

@app.route('/heatmap')
def heatmap():
    try:
        samples = query_preferred_dashboard_samples(f"SELECT * FROM {SAMPLE_MEASUREMENT};")
        if not samples:
            default_coords = (11.9228, 79.6268)
            m = folium.Map(location=default_coords, zoom_start=ZOOM_LEVEL_START)
            folium.Marker(default_coords, popup="<b>No data yet!</b>", icon=folium.Icon(color='blue', icon='info-sign')).add_to(m)
            return m._repr_html_()
        lats = measurements_list_to_field_value(samples, "lat")
        lons = measurements_list_to_field_value(samples, "lon")
        valid = [[float(la), float(lo)] for la, lo in zip(lats, lons) if la is not None and lo is not None]
        if not valid:
            m = folium.Map(location=(11.9228, 79.6268), zoom_start=12)
            return m._repr_html_()
        mean_coords = (float(np.mean([v[0] for v in valid])), float(np.mean([v[1] for v in valid])))
        m = folium.Map(location=mean_coords, zoom_start=ZOOM_LEVEL_START)
        HeatMap(valid).add_to(m)
        return m._repr_html_()
    except Exception as e:
        logging.error(f"Error in heatmap: {e}")
        return f"<h1>Error</h1><p>{str(e)}</p>"

@app.route('/last-location/')
def last():
    try:
        samples = query_preferred_dashboard_samples(f"SELECT * FROM {SAMPLE_MEASUREMENT} ORDER BY time DESC LIMIT 50;")
        if not samples:
            m = folium.Map(location=(11.9228, 79.6268), zoom_start=ZOOM_LEVEL_START)
            return m._repr_html_()
        s_data = samples[0]
        db_val = get_db_value(s_data)
        location = (float(s_data["lat"]), float(s_data["lon"]))
        m = folium.Map(location=location, zoom_start=ZOOM_LEVEL_START)
        folium.Marker(location, popup=f"<i>Time: {s_data['time']}, sound: {round(db_val, 1)} dB</i>").add_to(m)
        return m._repr_html_()
    except Exception as e:
        logging.error(f"Error in last-location: {e}")
        return f"<h1>Error</h1><p>{str(e)}</p>"

@app.route('/last-session/')
def last_session():
    try:
        latest_samples = query_preferred_dashboard_samples(f"SELECT * FROM {SAMPLE_MEASUREMENT} ORDER BY time DESC LIMIT 50;")
        if not latest_samples: return folium.Map(location=(11.9228, 79.6268), zoom_start=ZOOM_LEVEL_START)._repr_html_()
        last_session_id = latest_samples[0]["session_uuid"]
        samples = live_samples_only(query_points(f"SELECT * FROM {SAMPLE_MEASUREMENT} WHERE session_uuid='{last_session_id}';"))
        lat_values = [to_float(lat) for lat in measurements_list_to_field_value(samples, "lat") if lat is not None]
        lon_values = [to_float(lon) for lon in measurements_list_to_field_value(samples, "lon") if lon is not None]
        mean_coords = (float(np.mean(lat_values)), float(np.mean(lon_values)))
        m = folium.Map(location=mean_coords, zoom_start=ZOOM_LEVEL_START)
        for s in samples:
            db_val = get_db_value(s)
            folium.Marker((float(s["lat"]), float(s["lon"])), popup=f"<i>Time: {s['time']}, sound: {round(db_val, 1)} dB</i>").add_to(m)
        return m._repr_html_()
    except Exception as e:
        logging.error(f"Error in last-session: {e}")
        return f"<h1>Error</h1><p>{str(e)}</p>"

@app.route('/api/inject-demo', methods=['POST'])
def inject_demo():
    try:
        noise_types = ["Traffic", "Siren", "Speech", "Music", "Animal", "Silence", "Gunshot"]
        points = []
        for i in range(25):
            city_lat, city_lon, city_name = INDIAN_DEMO_CITIES[i % len(INDIAN_DEMO_CITIES)]
            lat = city_lat + (np.random.random() - 0.5) * 0.03
            lon = city_lon + (np.random.random() - 0.5) * 0.03
            nt = np.random.choice(noise_types)
            db_raw = -60 + np.random.random() * 40 
            points.append({
                "measurement": SAMPLE_MEASUREMENT,
                "tags": {"session_uuid": "demo-india-" + str(uuid.uuid4())[:8], "noise_class_tag": nt, "test": "True", "city": city_name},
                "fields": {
                    "lat": float(lat), "lon": float(lon), "sound_db": float(db_raw),
                    "sound_peak": float(db_raw / 100.0) + 0.1,
                    "sound_rms": float(db_raw / 100.0),
                    "sound_rms_db": float(db_raw - 2.0),
                    "confidence": float(0.85 + np.random.random() * 0.1),
                    "spectral_centroid": float(500 + np.random.random() * 2000),
                    "spectral_rolloff": float(750 + np.random.random() * 3000),
                    "zero_crossing_rate": float(0.01 + np.random.random() * 0.1),
                    "duration_s": float(2.0 + np.random.random() * 3.0),
                    "user_name": f"🚀 Demo Bot ({city_name})"
                },
                "time": datetime.utcnow().isoformat()
            })
        INFLUXDBCLIENT.write_points(points)
        return flask.jsonify({"status": "success"})
    except Exception as e:
        return flask.jsonify({"error": str(e)}), 500

@app.route('/api/clear-demo', methods=['POST'])
def clear_demo():
    try:
        INFLUXDBCLIENT.query(f"DROP SERIES FROM {SAMPLE_MEASUREMENT} WHERE test='True'")
        return flask.jsonify({"status": "success"})
    except Exception as e:
        return flask.jsonify({"error": str(e)}), 500

@app.route('/dashboard')
def dashboard():
    return flask.render_template('./dashboard.html')

@app.route('/api/stats')
def api_stats():
    try:
        samples = query_preferred_dashboard_samples(f"SELECT * FROM {SAMPLE_MEASUREMENT} ORDER BY time DESC LIMIT 500;")
        if not samples: return flask.jsonify({"avg_db": 0, "peak_db": 0, "total_samples": 0})
        db_levels = [get_db_value(s) for s in samples]
        classes = {}
        for s in samples:
            c = display_noise_class(s)
            classes[c] = classes.get(c, 0) + 1
        top_class = max(classes, key=lambda key: classes[key]) if classes else "N/A"
        conf_list = [((s.get("confidence") or 0) * 100 if (s.get("confidence") or 0) <= 1.0 else (s.get("confidence") or 0)) for s in samples]
        zcr_list = [s.get("zero_crossing_rate", 0) or s.get("zcr", 0) for s in samples if (s.get("zero_crossing_rate") is not None or s.get("zcr") is not None)]
        centroid_list = [s.get("spectral_centroid", 0) for s in samples if s.get("spectral_centroid") is not None]
        return flask.jsonify({
            "avg_db": round(sum(db_levels)/len(db_levels), 2) if db_levels else 0,
            "peak_db": round(max(db_levels), 2) if db_levels else 0,
            "top_class": top_class, "total_samples": len(samples),
            "avg_confidence": round(sum(conf_list)/len(conf_list), 1) if conf_list else 0,
            "avg_zcr": round(sum(zcr_list)/len(zcr_list), 4) if zcr_list else 0,
            "avg_centroid": round(sum(centroid_list)/len(centroid_list), 1) if centroid_list else 0
        })
    except Exception as e:
        return flask.jsonify({"error": str(e)}), 500

@app.route('/api/samples')
def api_samples():
    try:
        hours = int(flask.request.args.get('hours', 168))
        min_conf = float(flask.request.args.get('min_conf', flask.request.args.get('min_confidence', 0)))
        n_class = flask.request.args.get('class', 'All Classes')
        include_test = flask.request.args.get('include_test', 'false').lower() in {'1', 'true', 'yes'}
        query = f"SELECT * FROM {SAMPLE_MEASUREMENT} WHERE time > now() - {hours}h"
        if n_class not in ['All Classes', 'all']: query += f" AND noise_class = '{n_class}'"
        result = query_points(query + " ORDER BY time DESC LIMIT 1000")
        # Always pass include_test=True so demo data shows when no real data exists
        result = preferred_dashboard_samples(result, include_test=True)
        samples = []
        for s in result:
            raw_conf = s.get("confidence") or 0
            display_conf = round(raw_conf * 100, 1) if raw_conf <= 1.0 else round(raw_conf, 1)
            if display_conf < (min_conf * 100): continue
            if s.get("lat") is None or s.get("lon") is None: continue
            db_val = get_db_value(s)
            samples.append({
                "time": s.get("time"), "lat": to_float(s.get("lat")), "lon": to_float(s.get("lon")), "sound_db": round(db_val, 2),
                "noise_class": display_noise_class(s), "confidence": display_conf,
                "sound_peak": round(s.get("sound_peak", 0) or s.get("peak_amplitude", 0) or 0, 4),
                "sound_rms": round(s.get("sound_rms", 0) or s.get("rms_db", 0) or 0, 4),
                "spectral_centroid": round(s.get("spectral_centroid", 0) or 0, 1),
                "spectral_rolloff": round(s.get("spectral_rolloff", 0) or 0, 1),
                "zero_crossing_rate": round(s.get("zero_crossing_rate", 0) or s.get("zcr", 0) or 0, 4),
                "audio_filename": s.get("audio_filename"), "session_uuid": s.get("session_uuid"),
                "user_name": s.get("user_name", "Anonymous"), "duration_s": s.get("duration_s", 5.0)
            })
        return flask.jsonify(samples)
    except Exception as e:
        return flask.jsonify([]), 200

@app.route('/api/chart-data')
def api_chart_data():
    try:
        samples = query_preferred_dashboard_samples(f"SELECT * FROM {SAMPLE_MEASUREMENT} ORDER BY time DESC LIMIT 500;")
        if not samples: return flask.jsonify({"class_dist": {}, "db_over_time": []})
        class_dist = {}
        db_over_time = []
        for s in samples:
            nc = display_noise_class(s)
            class_dist[nc] = class_dist.get(nc, 0) + 1
            db_val = get_db_value(s)
            if s.get("time"): db_over_time.append({"t": str(s.get("time")), "db": round(db_val, 2)})
        return flask.jsonify({"class_dist": class_dist, "db_over_time": list(reversed(db_over_time))[-50:]})
    except Exception as e:
        return flask.jsonify({"error": str(e)}), 500

@app.route('/api/generate-report', methods=['POST'])
def generate_report():
    try:
        samples = query_preferred_dashboard_samples(f"SELECT * FROM {SAMPLE_MEASUREMENT} ORDER BY time DESC LIMIT 200;")
        if not samples: return flask.jsonify({"error": "No data"}), 400
        db_levels = [get_db_value(s) for s in samples]
        events = [f"Class: {display_noise_class(s)}, dB: {round(get_db_value(s),1)}, Conf: {round((s.get('confidence',0)*100 if s.get('confidence',0)<=1.0 else s.get('confidence',0)),1)}%" for s in samples[:15]]
        prompt = f"Professional Acoustic Report. Samples: {len(samples)}, Avg dB: {round(sum(db_levels)/len(db_levels),2)}, Peak: {round(max(db_levels),2)}. Events: {chr(10).join(events)}"
        if not api_key: return flask.jsonify({"error": "No API Key"}), 500
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
        resp = requests.post(url, json={"contents": [{"parts": [{"text": prompt}]}]})
        return flask.jsonify({"report_markdown": resp.json()['candidates'][0]['content']['parts'][0]['text']})
    except Exception as e:
        return flask.jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=True)
