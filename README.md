# 🌍 Smart City Acoustic Forensics & Noise Mapping System

Welcome to the **Smart Noise Mapping System** – an end-to-end IoT, Machine Learning, and Generative AI pipeline designed to crowdsource, classify, and visualize urban acoustic data in real-time. 

This project acts as a "Waze for Noise Pollution", empowering citizens to record environmental sounds while providing city planners with actionable, AI-driven acoustic forensic reports.

---

## 🚀 Features

* **📱 Mobile App (Flutter):** A sleek, cross-platform mobile application that records 5-second raw audio bursts, captures precise GNSS/GPS coordinates, and pushes the payload to the local backend.
* **🧠 Machine Learning (YAMNet):** A dedicated Python consumer that processes incoming audio queues using Google's **YAMNet** Deep Learning model to classify 521 distinct environmental sounds (e.g., Speech, Traffic, Sirens, Music).
* **📊 Time-Series Database:** All processed acoustic metadata (RMS Amplitude, Peak Amplitude, Zero Crossing Rate, Spectral Centroids) is efficiently stored in **InfluxDB**.
* **🗺️ Live Global Dashboard:** A dynamic Web UI built with Leaflet.js that automatically polls the database and plots real-time colored markers based on noise intensity and classification.
* **📈 Advanced Analytics:** Full **Grafana** integration for deep-dive visualizations of acoustic trends over time.
* **✨ Generative AI Reports:** A one-click "AI Report" feature that pipes database aggregates into Google's **Gemini 2.5 Flash** model to generate and export professional, downloadable PDF acoustic forensic reports.

---

## 🏗️ System Architecture

The entire backend is orchestrated using **Docker Compose** for seamless deployment and scaling.

1. **Flutter App** -> `POST /collect` -> **Flask API**
2. **Flask API** -> Publishes raw data to **MQTT Broker (Mosquitto)**
3. **ML Consumer** -> Subscribes to MQTT -> Runs YAMNet inference -> Saves to **InfluxDB**
4. **Flask Dashboard / Grafana** -> Queries InfluxDB for real-time visualization
5. **Gemini REST API** -> Reads InfluxDB aggregates -> Generates PDF Report

---

## ⚙️ Prerequisites

Before you begin, ensure you have met the following requirements:
* **Docker** & **Docker Compose** installed on your host machine.
* **Flutter SDK** installed for the mobile application.
* A valid **Google Gemini API Key**.

---

## 🛠️ Installation & Setup

### 1. Clone the Repository
```bash
git clone https://github.com/adarshaldkar/smart-noise-mapping-system.git
cd smart-noise-mapping-system
```

### 2. Configure Environment Variables
Inside the `noise_mapper` backend folder, open `docker-compose.yml` and insert your Gemini API Key in the `noisemapper_api` service section:
```yaml
environment:
  - GEMINI_API_KEY=your_actual_api_key_here
```

### 3. Start the Backend Infrastructure
Navigate to the backend directory and spin up the Docker containers:
```bash
cd noise_mapper
docker-compose up --build -d
```
This single command will boot up:
* **Flask API** on `http://localhost:5000`
* **Grafana** on `http://localhost:3000`
* **InfluxDB** on `http://localhost:8086`
* **Mosquitto MQTT** on `port 1883`
* **ML Audio Consumer** (runs in background)

### 4. Configure the Mobile App
You must point the Flutter app to your laptop's IP address so it knows where to send the audio data.
1. Find your IPv4 address (e.g., `192.168.1.5`). *Tip: Using a mobile hotspot guarantees a stable local IP.*
2. Open `noise_mapper_app/lib/services/api_service.dart`.
3. Update the fallback IP, or simply open the App's **Settings Screen** on your phone and type in your IP address.

### 5. Run the Mobile App
Connect your Android/iOS device and run:
```bash
cd noise_mapper_app
flutter run
```

---

## 🎮 Usage Guide

1. **Start Mapping:** Open the Flutter app on your phone, ensure location permissions are granted, and tap **START MAPPING**. The app will record and upload audio.
2. **View the Map:** Open `http://localhost:5000/dashboard` on your laptop. You will see your real-time location plotted on the map.
3. **Generate AI Report:** Click the **"✨ AI Report"** button on the dashboard. The system will analyze the recent data and generate a printable PDF Smart City Forensic Report.
4. **Advanced Analytics:** Open `http://localhost:3000` to view the Grafana dashboard. Login with `admin` / `admin`.

---

## 🛠️ Technology Stack
* **Frontend Mobile:** Flutter, Dart
* **Backend API:** Python, Flask, Gunicorn
* **Message Broker:** Eclipse Mosquitto (MQTT)
* **Machine Learning:** TensorFlow, YAMNet, Librosa, SciPy
* **Databases:** InfluxDB
* **Data Visualization:** HTML5, Leaflet.js, Grafana
* **Generative AI:** Google Gemini 2.5 Flash (REST API)

---

## 👨‍💻 Developed By
Developed by Adarsh and Team for the Final Year Engineering Project.
