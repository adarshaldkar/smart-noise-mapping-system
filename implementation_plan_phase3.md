# Phase 3: Premium Viva Features & AI Integration

This plan covers the final, high-impact features designed specifically to impress during an academic viva presentation. It transitions the project from a working prototype into a fully-fledged smart city analytics platform with AI and forensic capabilities.

## User Review Required

> [!IMPORTANT]  
> **Gemini API Key Required:** For the AI-generated report, we will need a Google Gemini API Key. Do you already have one, or would you like me to show you how to get a free one when we reach that step?

> [!NOTE]
> **Audio Storage:** Saving every audio file will take up disk space over time. Since this is for a college project, storing them locally in the Docker container's `static/` folder is perfectly fine.

## Proposed Changes

### 1. Map Colors & Strict Legend (Website)
- **Modify** `api/templates/dashboard.html` to base the map square colors mathematically on the `sound_db` value rather than the AI class.
  - 🟢 **Green (Safe):** < 45 dB
  - 🟡 **Yellow (Moderate):** 45 dB - 65 dB
  - 🟠 **Orange (Loud):** 66 dB - 85 dB
  - 🔴 **Red (Hazardous):** > 85 dB
- **Add** a permanent, floating Legend UI box to the bottom right of the Leaflet map explaining these thresholds.

### 2. Audio Storage & Playback (Backend + Website)
#### [MODIFY] `consumer/main.py`
- Update the MQTT listener to save the incoming audio bytes as a `.wav` file in a shared volume (e.g., `api/static/audio/`).
- Generate a unique filename using the `session_uuid` and `timestamp`.
- Write the `audio_filename` string into InfluxDB alongside the dB and ML metrics.

#### [MODIFY] `api/templates/dashboard.html`
- Update the Leaflet map popup logic. If an `audio_filename` exists for a point, inject an `<audio controls src="/static/audio/..."></audio>` tag so the user can listen to the exact noise.

### 3. Flutter App: User Personalization
#### [MODIFY] `noise_mapper_app/lib/screens/home_screen.dart`
- Add a sleek text input field at the top of the screen asking for the "Mapper's Name" (e.g., Shruti).
- Save this name to `shared_preferences` so it persists between app launches.

#### [MODIFY] `noise_mapper_app/lib/services/api_service.dart`
- Include the `user_name` in the multipart JSON payload sent to the backend.
- Update the website dashboard to display "Mapped by: [Name]" in the forensic popups.

### 4. Interactive Test Demo Script
#### [NEW] `noise_mapper/scripts/run_demo_simulation.py`
- Create a Python script designed specifically for the viva presentation.
- It will programmatically upload 3 specific test cases using real Indian coordinates:
  1. **Gunshot** (Red square, Delhi coordinates)
  2. **Heavy Traffic** (Orange square, Mumbai coordinates)
  3. **Dog Barking/Animal** (Yellow square, Bangalore coordinates)
- The script will allow you to instantly populate the map with interesting, diverse data.

### 5. AI Session Report & PDF Download
#### [NEW] `api/templates/report.html` & [MODIFY] `api/main.py`
- Add a new endpoint `/api/generate-report` that fetches all InfluxDB data for the *Last Session*.
- Send a prompt to the **Google Gemini API** containing the data averages (e.g., "50 samples, peak 95dB, mostly traffic").
- Gemini will return a professional, human-readable summary.
- Display this report on the dashboard and use **jsPDF** to allow the user to click a "Download as PDF" button.

---

## Verification Plan

### Automated Tests
- Run `run_demo_simulation.py` and verify that the 3 test points immediately appear on the map in Delhi, Mumbai, and Bangalore.
- Verify that clicking the Delhi point shows the AI Class as "Gunshot" and the color is Red (> 85 dB).

### Manual Verification
- Enter a name in the Flutter app, record a sound, and verify the name appears on the dashboard.
- Click "Play" on the dashboard popup and verify the audio plays correctly.
- Click "Generate AI Report", verify the text makes sense, and successfully download the PDF.
