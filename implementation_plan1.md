# Phase 2: Master Frontend Roadmap

Based on the combined feature lists, we have distilled the roadmap into the highest-impact features that will transform this project from a prototype into a robust, professional-grade system (perfect for academic evaluation and smart-city pitches).

This plan is divided into the **Flutter Mobile App** (the edge device) and the **Website Map** (the central dashboard).

---

## Part A: Flutter Mobile App Upgrades

The goal for the app is **stability, transparency, and a premium aesthetic**. We want the user to trust the app and clearly see the acoustic data they are gathering.

### 1. Robust Capture & Offline Sync (MVP / Top Priority)
- **Clear State UI:** Visual transitions between `Recording` ➔ `Uploading` ➔ `Success/Failed`.
- **Offline Queue + Auto-Sync:** (Massive evaluator bonus). If the phone loses 4G/Wi-Fi, audio and GPS data are cached locally using SQLite/SharedPrefs. Once the network returns, a background worker automatically syncs the queue.
- **Retry Logic:** Automatic retry for failed API uploads.

### 2. Live Recording Dashboard & Session Tracking
- **Live dB Visualizer:** A large, responsive audio waveform or decibel meter in the center of the screen so it looks like a real acoustic measuring tool.
- **Session Telemetry:** Display the active `Session ID`, elapsed time, total samples captured, and upload success rate.
- **GPS Signal Indicator:** A live status bar showing GPS accuracy (e.g., "High Accuracy (3m)" or "Searching for satellites...") so the user knows if their location is valid before recording.

### 3. Real-Time Map Preview
- **Integrated Map Tab:** A secondary screen utilizing `flutter_map` or Google Maps to show the user's current path (breadcrumb trail) and the noise points they've dropped during the current session, preventing them from needing to open the website while walking.

---

## Part B: Website & Map Dashboard Upgrades

The goal for the website is **traceability, filtering, and data visualization**. We want to prove the data is scientific and actionable.

### 1. Interactive & Filterable Map (MVP / Top Priority)
- **Advanced Filters:** Add a UI control panel to the Folium/Leaflet map allowing filtering by:
  - Date & Time range.
  - Noise Class (e.g., Show only "Traffic" or "Construction").
  - Confidence Threshold (e.g., Only show classifications > 75% confidence).
- **Click-to-Inspect Details:** Clicking any heatmap cell or marker reveals a detailed popup showing: `Timestamp`, `dB Level`, `Noise Class`, `Confidence %`, and `Session ID`. (Proves data traceability).

### 2. Live Dashboard & Analytics Panel
- **Real-Time Sidebar:** A live feed on the side of the map showing the most recent incoming noise samples and active mapping sessions.
- **Compact Analytics Cards:** 2–3 embedded charts (leveraging our Grafana queries or built via Chart.js) showing:
  - Top Noisy Zones.
  - Noise Class Distribution.
  - Average dB over the last 24 hours.

---

> [!IMPORTANT]
> ## User Review Required
> This is the synthesized "Best-Of" plan. 
> 
> **How shall we begin execution?** 
> I recommend starting with **Part A, Step 1 & 2** (Flutter UI states, Live dB Visualizer, and Offline Sync) as the mobile app is the entry point for all data. Let me know if you agree or if you prefer starting with the Website Map!
