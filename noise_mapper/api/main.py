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


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=True)
