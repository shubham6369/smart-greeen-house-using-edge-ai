# Smart Greenhouse Automation Using Edge AI
### Bringing Local Intelligence & Autonomous Control to Modern Agriculture

**B.Tech Computer Science & Engineering — Minor Project**  
**Babu Banarasi Das University (BBDU), Lucknow**

---

## 📌 Executive Summary

This project implements an end-to-end, production-grade **Smart Greenhouse Automation System** powered by **Edge AI**.

Traditional IoT greenhouse architectures rely on continuous cloud connectivity. In rural and peri-urban farm settings, intermittent internet outages cause delayed responses, crop damage, and potential pump runaways. 

Our system solves this by running **100% of telemetry acquisition, biophysical calculations, machine learning inference, and safety interlocks locally on the edge machine (laptop or Raspberry Pi) with sub-2-millisecond latency**.

```
                        ┌───────────────────────────────────────────────┐
                        │          Streamlit Web Dashboard              │
                        │      (Live Gauges, Scenarios & Charts)        │
                        └───────────────────────┬───────────────────────┘
                                                │
                        ┌───────────────────────▼───────────────────────┐
                        │             Edge Decision Engine              │
                        │  • Threshold Rule Engine (Hysteresis & Safety)│
                        │  • Offline Scikit-Learn ML (RandomForest)     │
                        │  • Tetens Equation Vapor Pressure Deficit     │
                        └───────────────┬───────────────┬───────────────┘
                                        │               │
              ┌─────────────────────────▼──┐         ┌──▼──────────────────────────┐
              │   Persistent SQLite DB     │         │    Hardware Bridge Driver   │
              │  (Local Event & Log Store) │         │    (PySerial / USB-UART)    │
              └────────────────────────────┘         └──────────────┬──────────────┘
                                                                    │ Serial (JSON)
                                                     ┌──────────────▼──────────────┐
                                                     │   ESP32 / Arduino Device    │
                                                     │  DHT22, Soil, LDR & Relays  │
                                                     └─────────────────────────────┘
```

---

## 🌟 Key Capabilities

1. **Multi-Modal Environmental Sensing:**
   - 🌡️ **Ambient Temperature (°C)** with high/low threshold monitoring.
   - 💧 **Relative Humidity (%)** with moisture saturation tracking.
   - 🌱 **Soil Moisture (%)** with capacitive/resistive sensor normalization.
   - ☀️ **Light Intensity (Lux)** for photosynthetic monitoring.
   - 🌾 **Vapor Pressure Deficit (VPD in kPa)** using the agronomic **Tetens equation**.

2. **Dual-Strategy Edge Intelligence:**
   - **Agronomic Rule Engine:** Evaluates closed-loop rules with **hysteresis bands** to prevent relay chatter and actuator wear.
   - **Local Machine Learning Engine:** Runs an offline **Scikit-Learn RandomForestClassifier** to predict crop stress (`Healthy`, `Water Stress`, `Heat Stress`, `Low Light`) in under 2 ms on standard CPU.

3. **Dual Operating Modes (Real Hardware & Digital Chamber Twin):**
   - **Physical Hardware Mode:** Auto-scans COM/TTY serial ports, connects to ESP32/Arduino via USB, reads live telemetry JSON, and controls 5V relay modules.
   - **Digital Chamber Simulator:** Simulates real-world environmental dynamics and actuator feedback loops without needing physical hardware connected.

4. **Fail-Safe Actuator Protections:**
   - **Irrigation Runaway Watchdog:** Shuts off the water pump if active past safety limits without soil moisture recovery.
   - **Relay Hysteresis:** Avoids rapid switching of fans near temperature boundaries.
   - **Global Emergency Stop:** Instantly opens all relays in hazardous conditions.

5. **Local Data Persistence & Telemetry Export:**
   - Logs every sensor reading, decision output, and actuator event to local **SQLite** (`data/greenhouse.db`).
   - Generates one-click **CSV exports** and interactive **Plotly** trend visualizations.

---

## 📂 Project Structure

```text
smart-greenhouse-using-edge-ai/
│
├── app.py                 # Streamlit web dashboard & system orchestrator
├── decision_engine.py     # Edge AI engine (Agronomic rules + Local ML + VPD)
├── hardware.py            # Microcontroller bridge, serial auto-detect & loopback emulator
├── simulator.py           # Digital chamber twin simulator with physics feedback
├── database.py            # Local SQLite database manager & CSV telemetry exporter
├── esp32_greenhouse.ino   # Microcontroller C++ firmware for ESP32 / Arduino
├── tests.py               # Automated unit & integration verification test suite
│
├── requirements.txt       # Python dependencies (Streamlit, Scikit-Learn, Plotly, PySerial)
├── README.md              # Complete project documentation & guide
└── TECHNOLOGY_USED.md     # Technology stack breakdown, formulas & architecture
```

---

## ⚡ Quick Start Guide

### Step 1: Clone or Navigate to Directory
```powershell
cd "c:\Users\hp\Desktop\smart greenhouse using edge ai"
```

### Step 2: Install Python Dependencies
```powershell
python -m pip install -r requirements.txt
```

### Step 3: Launch the Edge Dashboard
```powershell
python -m streamlit run app.py
```
Your default web browser will open at **`http://localhost:8501`**.

---

## 🧪 Automated Test Verification

Run the comprehensive test suite to verify sensor normalization, biophysics math, decision rules, edge ML inference, SQLite storage, and hardware loopback drivers:

```powershell
python tests.py
```

Expected Output:
```text
--- Running Smart Greenhouse Test Suite ---
[OK] Simulator & Sensor Validation: PASSED
[OK] Biophysics VPD (Tetens Equation): PASSED
[OK] Decision Rules & Safety Invariants: PASSED
[OK] Local Scikit-Learn Edge ML Inference: PASSED
[OK] Persistent SQLite Database: PASSED
[OK] Real Hardware Driver & Loopback Protocol: PASSED

[SUCCESS] ALL TESTS PASSED! (100% Ready for Evaluation / Production)
```

---

## 🔌 Hardware Wiring & Microcontroller Interface

If connecting physical hardware using [esp32_greenhouse.ino](file:///c:/Users/hp/Desktop/smart%20greenhouse%20using%20edge%20ai/esp32_greenhouse.ino):

| Component | Microcontroller Pin (ESP32) | Role |
| :--- | :--- | :--- |
| **DHT22 Sensor** | `GPIO 4` | Ambient Temperature & Relative Humidity |
| **Capacitive Soil Sensor** | `GPIO 34` (ADC) | Volumetric Soil Moisture Reading |
| **LDR Photoresistor** | `GPIO 35` (ADC) | Sunlight / Supplemental Light Level |
| **Relay 1 (Drip Pump)** | `GPIO 18` (Digital Out) | 12V DC Submersible Water Pump |
| **Relay 2 (Exhaust Fan)** | `GPIO 19` (Digital Out) | 12V DC Ventilation / Cooling Fan |
| **Relay 3 (Grow Light)** | `GPIO 21` (Digital Out) | Full-Spectrum LED Agricultural Array |

### Serial Packet Protocol:
- **Telemetry from Microcontroller to Python (every 2s):**
  ```json
  {"temp": 24.5, "hum": 65.0, "soil": 55.0, "light": 25000, "pump": 0, "fan": 0, "light_act": 0}
  ```
- **Actuation Command from Python to Microcontroller:**
  ```json
  {"cmd": "ACTUATE", "pump": 1, "fan": 0, "light": 0}
  ```

---

## 🧠 Code Architecture Summary

- **`app.py`**: Web interface built with Streamlit featuring 4 tabs:
  1. *Live Monitor & Controls*: Sensor metric gauges, scenario injector, manual switches, and reasoning logs.
  2. *Edge AI & Biophysics*: Live ML stress predictions, confidence score, and real-time VPD gauges.
  3. *Analytics & Data Export*: Interactive Plotly historical trend charts and CSV download.
  4. *System Diagnostics & Hardware Guide*: Active COM port selector, loopback testing, and circuit reference.
- **`decision_engine.py`**: Calculates VPD using the Tetens equation, runs safety threshold rules with deadbands, and infers plant stress states using an offline Scikit-Learn RandomForest classifier.
- **`simulator.py`**: Models greenhouse thermodynamics and soil hydrology; dynamically updates environmental values based on actuator states.
- **`hardware.py`**: Scans available serial ports, handles JSON framing over UART, manages timeouts, and includes an in-memory loopback driver for hardware-free driver testing.
- **`database.py`**: Manages persistent SQLite tables (`telemetry` and `actuator_events`) and handles CSV formatting for offline agronomic records.

---

## 👥 Project & Department Details
- **Department:** Computer Science & Engineering
- **University:** Babu Banarasi Das University (BBDU), Lucknow
- **Topic:** Smart Greenhouse Automation Using Edge AI
