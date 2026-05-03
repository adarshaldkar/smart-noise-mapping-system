# Phase 2: Frontend & Mobile App Upgrades

Now that the backend analytics engine (InfluxDB + Grafana + Machine Learning) is running perfectly, it's time to transition to the frontend.

Currently, the `noise_mapper_app` Flutter UI is a very basic sensor node (a pulsing circle and a "Start Mapping" button). Based on the premium design goals of the project, we need to make it look and feel like an advanced acoustic tool.

## Proposed Frontend Upgrades (Choose What You Want!)

### 1. 🌡️ Live Decibel / Visualizer UI
Instead of a simple pulsing red circle, we can upgrade `home_screen.dart` to feature a **Live Decibel Meter** or Audio Waveform visualizer. Even though the heavy lifting (ML, Spectral Centroid) happens on the server, we can measure raw dB locally on the phone to give the user instant feedback that sound is being captured.

### 2. 🗺️ Integrated Noise Map View
Right now, you have to open a web browser to see the map or Grafana. We can add a second tab to the Flutter app called **"Live Map"** using a `WebView`. This will embed your Folium Map or Grafana dashboards directly inside the mobile app, allowing you to see the map updating as you walk around.

### 3. 🤖 AI Feedback Loop
We can modify the API so that after the phone sends a 5-second audio clip, the server immediately replies with the predicted `noise_class` (e.g., "Traffic", "Speech", "Construction"). The Flutter app can then display a pop-up: *"Server detected: Traffic Noise (85dB)"*.

### 4. 🎨 Premium Glassmorphic Design Upgrade
We can refactor the Flutter UI to have a highly polished, modern dark-mode aesthetic with smooth gradients, glassmorphism (frosted glass effects), and advanced micro-animations, ensuring it wows your professors/users during the presentation.

---

> [!IMPORTANT]
> ## User Review Required
> How would you like to proceed? Do you want to implement all of the above, or focus on a specific feature (like the Live Map or the AI Feedback Loop)? Let me know your priorities for the frontend!
