from influxdb import InfluxDBClient
from datetime import datetime
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

app = flask.Flask(__name__)

# Array logic removed - using dynamic HeatMap instead


def measurements_list_to_field_value(measurements, field_key):
    ret = []
    for measurement in measurements:
        ret.append(measurement.get(field_key, None))
    return ret


@app.route('/')
def index():
    return flask.render_template('./index.html')


@app.route('/noisemap')
def noisemap():
    t_i = datetime.now()

    try:
        result = list(INFLUXDBCLIENT.query("select * from samples where test!='True';"))
        if not result or len(result) == 0:
            # No data yet - return empty map with message
            default_coords = [41.39, 2.17]  # Barcelona area
            m = folium.Map(location=default_coords, zoom_start=ZOOM_LEVEL_START)
            folium.Marker(
                default_coords,
                popup="<b>No data yet!</b><br>Start the Android app to collect noise samples.",
                icon=folium.Icon(color='blue', icon='info-sign')
            ).add_to(m)
            return m._repr_html_()
        
        samples = result[0]
        lats = measurements_list_to_field_value(samples, "lat")
        lons = measurements_list_to_field_value(samples, "lon")
        sounds = measurements_list_to_field_value(samples, "sound")

        # Filter out any rows with missing coordinates or sound
        valid = [(la, lo, s) for la, lo, s in zip(lats, lons, sounds)
                 if la is not None and lo is not None]

        if not valid:
            default_coords = [20.0, 78.0]  # India center as fallback
            m = folium.Map(location=default_coords, zoom_start=5)
            folium.Marker(default_coords,
                          popup="<b>No valid data yet!</b>",
                          icon=folium.Icon(color='blue', icon='info-sign')).add_to(m)
            return m._repr_html_()

        lats  = [v[0] for v in valid]
        lons  = [v[1] for v in valid]
        sounds = [v[2] for v in valid]

        # Auto-zoom to wherever the data actually is
        min_lat, max_lat = min(lats), max(lats)
        min_lon, max_lon = min(lons), max(lons)
        center = [(min_lat + max_lat) / 2, (min_lon + max_lon) / 2]

        m = folium.Map(location=center, zoom_start=15, tiles="OpenStreetMap")
        m.fit_bounds([[min_lat - 0.05, min_lon - 0.05], [max_lat + 0.05, max_lon + 0.05]])

        # Try to get noise_class if available
        try:
            noise_classes = measurements_list_to_field_value(result[0], "noise_class")
            # re-filter to match valid rows
            all_lats_raw = measurements_list_to_field_value(result[0], "lat")
            noise_classes = [noise_classes[i] for i, la in enumerate(all_lats_raw)
                             if la is not None]
        except Exception:
            noise_classes = [None] * len(lats)

        # Draw blocky square rectangles
        for i, lat in enumerate(lats):
            s = sounds[i]
            if s is None:
                s = 0.0
            # Determine color based on sound intensity
            intensity = s * 50
            if intensity > 0.6:
                color = "red"
            elif intensity > 0.3:
                color = "orange"
            elif intensity > 0.15:
                color = "yellow"
            else:
                color = "green"

            # Squares sized relative to zoom (0.0004 deg ≈ 40m at zoom 15)
            offset = 0.0004
            bounds = [[lat - offset, lons[i] - offset],
                      [lat + offset, lons[i] + offset]]

            nc = noise_classes[i] if i < len(noise_classes) else None
            noise_label = nc if (nc and nc not in ("None", "null")) else "Unknown"
            tooltip_text = f"{noise_label} | Level: {round(s * 100, 2)} dB"

            folium.Rectangle(
                bounds=bounds,
                color=color,
                fill=True,
                fill_color=color,
                fill_opacity=0.75,
                weight=1,
                tooltip=tooltip_text
            ).add_to(m)

        fig = branca.element.Figure(height="100%")
        fig.add_child(m)

        t_f = datetime.now()
        point_out = {
            "measurement": "metrics",
            "fields": {"api_response_time": (t_f - t_i).total_seconds()},
            "time": t_f
        }
        INFLUXDBCLIENT.write_points([point_out])

        return m._repr_html_()
    except Exception as e:
        logging.error(f"Error in noisemap: {e}")
        return f"<h1>Error</h1><p>{str(e)}</p><p>Please check the logs.</p>"


@app.route('/collect', methods=['POST'])
def collect():
    try:
        # 1. Get the JSON metadata and audio file
        metadata_str = flask.request.form.get('metadata')
        if not metadata_str:
            return flask.jsonify({"error": "No metadata provided"}), 400
            
        metadata = json.loads(metadata_str)
        
        if 'audio' not in flask.request.files:
            return flask.jsonify({"error": "No audio file provided"}), 400
            
        audio_file = flask.request.files['audio']
        audio_bytes = audio_file.read()
        
        # Save audio file for playback on dashboard
        audio_dir = os.path.join(app.root_path, 'static', 'audio')
        os.makedirs(audio_dir, exist_ok=True)
        # Use session_uuid and time to create a unique filename
        filename = f"{metadata.get('session_uuid', 'unknown')}_{metadata.get('time', int(time.time()))}.wav"
        filepath = os.path.join(audio_dir, filename)
        with open(filepath, 'wb') as f:
            f.write(audio_bytes)
            
        metadata["audio_filename"] = filename
        
        # 2. Publish to MQTT broker so the consumer picks it up
        broker_host = "mosquitto"
        
        msgs = [
            {"topic": "pos", "payload": json.dumps(metadata), "qos": 0, "retain": False},
            {"topic": str(metadata["time"]), "payload": audio_bytes, "qos": 0, "retain": False}
        ]
        
        publish.multiple(msgs, hostname=broker_host, port=1883)
        
        return flask.jsonify({"status": "success", "message": "Data forwarded to ML pipeline"}), 200
        
    except Exception as e:
        logging.error(f"Error in /collect endpoint: {e}")
        return flask.jsonify({"error": str(e)}), 500


@app.route('/heatmap')
def heatmap():
    try:
        result = list(INFLUXDBCLIENT.query("select * from samples where test!='True';"))
        if not result or len(result) == 0:
            default_coords = [41.39, 2.17]
            m = folium.Map(location=default_coords, zoom_start=ZOOM_LEVEL_START)
            folium.Marker(
                default_coords,
                popup="<b>No data yet!</b><br>Start the Android app to collect noise samples.",
                icon=folium.Icon(color='blue', icon='info-sign')
            ).add_to(m)
            return m._repr_html_()
        
        samples = result[0]
        lats = measurements_list_to_field_value(samples, "lat")
        lons = measurements_list_to_field_value(samples, "lon")

        mean_coords = [np.mean(lats), np.mean(lons)]
        m = folium.Map(location=mean_coords, zoom_start=ZOOM_LEVEL_START)

        heat_data = []
        for i, lat in enumerate(lats):
            heat_data.append([lat, lons[i]])
        HeatMap(heat_data).add_to(m)

        fig = branca.element.Figure(height="100%")
        fig.add_child(m)

        return m._repr_html_()
    except Exception as e:
        logging.error(f"Error in heatmap: {e}")
        return f"<h1>Error</h1><p>{str(e)}</p>"


@app.route('/last-location/')
def last():
    try:
        result = list(INFLUXDBCLIENT.query("select * from samples where test!='True' order by time desc limit 1;"))
        if not result or len(result) == 0:
            default_coords = [41.39, 2.17]
            m = folium.Map(location=default_coords, zoom_start=ZOOM_LEVEL_START)
            folium.Marker(
                default_coords,
                popup="<b>No data yet!</b><br>Start the Android app to collect noise samples.",
                icon=folium.Icon(color='blue', icon='info-sign')
            ).add_to(m)
            return m._repr_html_()
        
        samples = result[0]
        lat = samples[0]["lat"]
        lon = samples[0]["lon"]
        sound = samples[0]["sound"]
        time = samples[0]["time"]

        m = folium.Map(location=[lat, lon], zoom_start=ZOOM_LEVEL_START)
        folium.Marker([lat, lon], popup=f"<i>Time: {time}, sound: {sound}</i>").add_to(m)

        fig = branca.element.Figure(height="100%")
        fig.add_child(m)

        return m._repr_html_()
    except Exception as e:
        logging.error(f"Error in last-location: {e}")
        return f"<h1>Error</h1><p>{str(e)}</p>"


@app.route('/last-session/')
def last_session():
    try:
        result = list(INFLUXDBCLIENT.query("select * from samples where test!='True' order by time desc limit 1;"))
        if not result or len(result) == 0:
            default_coords = [41.39, 2.17]
            m = folium.Map(location=default_coords, zoom_start=ZOOM_LEVEL_START)
            folium.Marker(
                default_coords,
                popup="<b>No data yet!</b><br>Start the Android app to collect noise samples.",
                icon=folium.Icon(color='blue', icon='info-sign')
            ).add_to(m)
            return m._repr_html_()
        
        last_sample = result[0]
        last_session = last_sample[0]["session_uuid"]
        samples = list(INFLUXDBCLIENT.query(f"select * from samples where test!='True' and session_uuid='{last_session}';"))[0]
        lats = measurements_list_to_field_value(samples, "lat")
        lons = measurements_list_to_field_value(samples, "lon")
        sounds = measurements_list_to_field_value(samples, "sound")
        times = measurements_list_to_field_value(samples, "time")

        mean_coords = [np.mean(lats), np.mean(lons)]
        m = folium.Map(location=mean_coords, zoom_start=ZOOM_LEVEL_START)

        for i, lat in enumerate(lats):
            folium.Marker([lat, lons[i]], popup=f"<i>Time: {times[i]}, sound: {sounds[i]}</i>").add_to(m)

        fig = branca.element.Figure(height="100%")
        fig.add_child(m)

        return m._repr_html_()
    except Exception as e:
        logging.error(f"Error in last-session: {e}")
        return f"<h1>Error</h1><p>{str(e)}</p>"


@app.route('/dashboard')
def dashboard():
    return flask.render_template('./dashboard.html')


@app.route('/api/stats')
def api_stats():
    """Returns summary stats for the dashboard cards."""
    try:
        result = list(INFLUXDBCLIENT.query("SELECT * FROM samples WHERE test!='True' ORDER BY time DESC LIMIT 200;"))
        if not result or len(result) == 0:
            return flask.jsonify({"total": 0, "avg_db": 0, "peak": 0, "top_class": "N/A", "avg_confidence": 0, "avg_zcr": 0, "avg_centroid": 0})

        samples = list(result[0])

        dbs       = [s.get("sound_db") for s in samples if s.get("sound_db") is not None]
        peaks     = [s.get("sound_peak") for s in samples if s.get("sound_peak") is not None]
        confs     = [s.get("confidence") for s in samples if s.get("confidence") is not None]
        zcrs      = [s.get("zero_crossing_rate") for s in samples if s.get("zero_crossing_rate") is not None]
        centroids = [s.get("spectral_centroid") for s in samples if s.get("spectral_centroid") is not None]
        classes   = [s.get("noise_class") for s in samples if s.get("noise_class")]

        top_class = max(set(classes), key=classes.count) if classes else "N/A"

        return flask.jsonify({
            "total":          len(samples),
            "avg_db":         round(np.mean(dbs), 2)       if dbs       else 0,
            "peak":           round(max(peaks), 4)          if peaks     else 0,
            "top_class":      top_class,
            "avg_confidence": round(np.mean(confs) * 100, 1) if confs   else 0,
            "avg_zcr":        round(np.mean(zcrs), 4)       if zcrs      else 0,
            "avg_centroid":   round(np.mean(centroids), 1)  if centroids else 0,
        })
    except Exception as e:
        logging.error(f"Error in /api/stats: {e}")
        return flask.jsonify({"error": str(e)}), 500


@app.route('/api/samples')
def api_samples():
    """Returns recent samples for the map and table. Supports filters."""
    try:
        noise_class = flask.request.args.get("class", None)
        min_conf    = float(flask.request.args.get("min_conf", 0))
        hours       = int(flask.request.args.get("hours", 24))

        query = f"SELECT * FROM samples WHERE test!='True' AND time > now() - {hours}h"
        if noise_class and noise_class != "all":
            query += f" AND noise_class='{noise_class}'"
        query += " ORDER BY time DESC LIMIT 500;"

        result = list(INFLUXDBCLIENT.query(query))
        if not result or len(result) == 0:
            return flask.jsonify([])

        samples = []
        for s in result[0]:
            conf = s.get("confidence", 0) or 0
            if conf < min_conf:
                continue
            if s.get("lat") is None or s.get("lon") is None:
                continue
            samples.append({
                "time":       s.get("time", ""),
                "lat":        s.get("lat"),
                "lon":        s.get("lon"),
                "sound_db":   round(s.get("sound_db", 0) or 0, 2),
                "sound_peak": round(s.get("sound_peak", 0) or 0, 4),
                "sound_rms":  round(s.get("sound_rms", 0) or 0, 4),
                "noise_class":       s.get("noise_class", "Unknown"),
                "confidence":        round(conf * 100, 1),
                "zero_crossing_rate": round(s.get("zero_crossing_rate", 0) or 0, 4),
                "spectral_centroid":  round(s.get("spectral_centroid", 0) or 0, 1),
                "spectral_rolloff":   round(s.get("spectral_rolloff", 0) or 0, 1),
                "duration_s":         round(s.get("duration_s", 0) or 0, 2),
                "session_uuid":       s.get("session_uuid", ""),
                "audio_filename":     s.get("audio_filename", ""),
                "user_name":          s.get("user_name", "Anonymous"),
            })
        return flask.jsonify(samples)
    except Exception as e:
        logging.error(f"Error in /api/samples: {e}")
        return flask.jsonify({"error": str(e)}), 500


@app.route('/api/chart-data')
def api_chart_data():
    """Returns aggregated chart data: class distribution + dB over time."""
    try:
        result = list(INFLUXDBCLIENT.query("SELECT * FROM samples WHERE test!='True' ORDER BY time DESC LIMIT 500;"))
        if not result or len(result) == 0:
            return flask.jsonify({"class_dist": {}, "db_over_time": []})

        samples = list(result[0])
        class_dist = {}
        db_over_time = []

        for s in samples:
            nc = s.get("noise_class", "Unknown") or "Unknown"
            class_dist[nc] = class_dist.get(nc, 0) + 1

            db_val = s.get("sound_db")
            t_val  = s.get("time")
            if db_val is not None and t_val is not None:
                db_over_time.append({"t": str(t_val), "db": round(db_val, 2)})

        # Reverse so chart shows oldest -> newest
        db_over_time = list(reversed(db_over_time))[-50:]

        return flask.jsonify({
            "class_dist":   class_dist,
            "db_over_time": db_over_time,
        })
    except Exception as e:
        logging.error(f"Error in /api/chart-data: {e}")
        return flask.jsonify({"error": str(e)}), 500


@app.route('/api/generate-report', methods=['GET', 'POST'])
def generate_report():
    """Generates an AI report of the acoustic data using Gemini."""
    try:
        # 1. Fetch recent data (e.g. all points)
        result = list(INFLUXDBCLIENT.query("SELECT * FROM samples WHERE test!='True' ORDER BY time DESC LIMIT 200;"))
        if not result or len(result) == 0:
            return flask.jsonify({"error": "No data available to generate a report."}), 400
            
        samples = list(result[0])
        
        # 2. Compute aggregate statistics for the AI
        total_samples = len(samples)
        db_levels = [s.get("sound_db") for s in samples if s.get("sound_db") is not None]
        avg_db = sum(db_levels) / len(db_levels) if db_levels else 0
        peak_db = max(db_levels) if db_levels else 0
        
        classes = {}
        for s in samples:
            c = s.get("noise_class", "Unknown") or "Unknown"
            classes[c] = classes.get(c, 0) + 1
            
        top_class = max(classes, key=classes.get) if classes else "Unknown"
        
        # Create a condensed list of events for the AI
        events = []
        for s in samples[:15]: # Send the last 15 specific events
            events.append(f"Class: {s.get('noise_class')}, dB: {round(s.get('sound_db', 0),1)}, Confidence: {round(s.get('confidence',0)*100,1)}%")

        # 3. Construct Prompt
        prompt = f"""You are a professional Smart City Acoustic Forensics AI.
Generate a structured, professional, executive summary report for a city's noise pollution based on the following real-time sensor data.

DATA SUMMARY:
- Total Samples Analyzed: {total_samples}
- Average dB Level: {round(avg_db, 2)} dB
- Peak dB Level: {round(peak_db, 2)} dB
- Most Common Noise Type: {top_class}

RECENT SIGNIFICANT EVENTS:
{chr(10).join(events)}

REQUIREMENTS:
1. Write the report in Markdown format.
2. Include the following sections:
   - Executive Summary
   - Acoustic Profile Analysis (explain what the dB levels and classes mean for livability)
   - Identified Anomalies / Hazards (if peak dB is > 75, highlight it)
   - Recommendations for Urban Planning
3. Keep it professional, objective, and around 200-300 words. Do not use generic pleasantries.
"""

        # 4. Generate Content with Gemini REST API
        if not api_key:
            return flask.jsonify({"error": "GEMINI_API_KEY environment variable is not set."}), 500
            
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
        headers = {'Content-Type': 'application/json'}
        data = {
            "contents": [{"parts": [{"text": prompt}]}]
        }
        
        resp = requests.post(url, headers=headers, json=data)
        if resp.status_code != 200:
            return flask.jsonify({"error": f"Gemini API returned {resp.status_code}: {resp.text}"}), 500
            
        result_json = resp.json()
        report_text = result_json['candidates'][0]['content']['parts'][0]['text']
        
        return flask.jsonify({"report_markdown": report_text})
        
    except Exception as e:
        logging.error(f"Error generating AI report: {e}")
        return flask.jsonify({"error": f"Failed to generate report: {str(e)}"}), 500


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=True)
