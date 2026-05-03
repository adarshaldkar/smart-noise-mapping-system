# Noise Mapper: AI Upgrade Plan

## 🧠 Phase 1: Machine Learning (Backend)
- [x] **Add ML Dependencies**: Include `tensorflow-cpu`, `tensorflow-hub`, and `librosa` in the Docker consumer environment.
- [x] **Build AI Classifier Component (`ml_classifier.py`)**:
    - Build a module to download and load Google's **YAMNet** audio classification model (recognizes 521 distinct environmental sounds).
    - Implement a resampling layer to convert raw audio into the required 16kHz mono format.
    - Run the AI model on the audio wave and calculate the confidence score for the dominant sound.
- [x] **Update Consumer Logic ([consumer/main.py](file:///c:/Users/shrut/Desktop/Final_year_project/noise_mapper/consumer/main.py))**:
    - Connect the AI model directly into the MQTT receiving data pipeline.
    - Extract the specific sound `class` and `confidence` alongside the raw decibel intensity.
    - Add fallback error handling (if ML fails to interpret a corrupt file, still record the dB level).
- [ ] **Update Database Schema**:
    - Send `noise_class` and `confidence` fields alongside standard data points to **InfluxDB**.
- [ ] **Test ML Accuracy**: Send test audio files locally and verify the AI predictions in the terminal logs.

## 📱 Phase 2: Mobile App (Flutter Frontend)
- [ ] **Create App Scaffold**: Initialize standard Flutter project (`noise_mapper_app`).
- [ ] **Install Plugins**: `geolocator` (GPS), `record` (Mic), `http` (Networking), `permission_handler` (Security).
- [ ] **Build Permission Logic**: Ask the user gracefully for "While Using" location access and Microphone access.
- [ ] **Build Recording Service**: Create logic to record 5-second audio chunks seamlessly while walking.
- [ ] **Build API Bridge**: Take the `.wav` / `.m4a` file + the live GPS coordinates, and do an HTTP POST to Flask (`/collect`).
- [ ] **Design Interface (UI)**:
    - Center glowing dB meter that pulses.
    - Large "Start Mapping" button.
    - Coordinates / altitude overlay.
    - History view to see past session records.

## 🗺️ Phase 3: Dynamic Data Visualization
- [ ] **Update Flask Backend ([api/main.py](file:///c:/Users/shrut/Desktop/Final_year_project/noise_mapper/api/main.py))**: Create the POST `/collect` route to absorb the phone data and push it into the MQTT broker or DB.
- [ ] **Dynamic Folium Map Filters**: Show customized markers or layers based on the `noise_class` (e.g., Red = Traffic, Yellow = Construction, Green = Nature).
