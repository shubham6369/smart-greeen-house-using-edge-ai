# Technology Stack & Architecture Specification
## Smart Greenhouse Automation Using Edge AI
**B.Tech Computer Science & Engineering — Minor Project**  
**Babu Banarasi Das University (BBDU), Lucknow**

---

## 🏛️ System Architecture Overview

The system is designed following a **multi-tiered Edge AI architecture** where telemetry acquisition, biophysical computations, machine learning inference, safety interlocks, and local database storage operate entirely on the edge machine (laptop or Raspberry Pi) without reliance on external cloud connectivity.

```
                      ┌───────────────────────────────────────────────┐
                      │          Streamlit Web Dashboard              │
                      │     (Interactive Controls & Visualizer)       │
                      └───────────────────────┬───────────────────────┘
                                              │
                      ┌───────────────────────▼───────────────────────┐
                      │              Edge Decision Engine             │
                      │  ┌────────────────────┬────────────────────┐  │
                      │  │ Agronomic Rules    │ Scikit-Learn ML    │  │
                      │  │ (Safety Thresholds)│ (RandomForest)     │  │
                      │  └────────────────────┴────────────────────┘  │
                      │  Biophysical Engine: VPD (Tetens Equation)    │
                      └───────────────┬───────────────┬───────────────┘
                                      │               │
            ┌─────────────────────────▼──┐         ┌──▼──────────────────────────┐
            │   Persistent SQLite DB     │         │   Hardware Abstraction      │
            │  (WAL Mode / CSV Exports)  │         │   (PySerial Bridge / Driver)│
            └────────────────────────────┘         └──────────────┬──────────────┘
                                                                  │ USB / UART (JSON)
                                                   ┌──────────────▼──────────────┐
                                                   │   ESP32 / Arduino Firmware  │
                                                   │  (Sensors & Relay Actuation)│
                                                   └─────────────────────────────┘
```

---

## 📋 Core Technologies & Justification

| Technology | Domain | Role in System | Justification |
| :--- | :--- | :--- | :--- |
| **Python 3.10+** | Core Programming | System Orchestration & Engine | Cross-platform runtime, rich scientific ecosystem, fast prototyping, runs on Raspberry Pi and laptops. |
| **Streamlit** | UI / Presentation | Edge Operator Web Dashboard | Pure-Python reactive frontend with automatic session management; eliminates web server and frontend build complexity. |
| **Scikit-Learn** | Edge Machine Learning | Plant Stress Classification | Lightweight `RandomForestClassifier` with deterministic CPU inference (< 2 ms latency) and zero GPU/cloud overhead. |
| **SQLite 3** | Embedded Database | Local Telemetry & Event Storage | Serverless, zero-configuration local ACID storage in a single portable file (`data/greenhouse.db`). |
| **Plotly** | Data Visualization | Real-Time Interactive Charts | Hardware-accelerated browser charting for multi-sensor environmental trends and setpoints. |
| **Pandas & NumPy** | Data Engineering | Data Transformation & CSV Export | Fast vector operations, sliding-window calculations, and structured data serialization. |
| **PySerial** | Hardware Interfacing | Microcontroller Communication | Robust RS-232 / USB-CDC serial interface with port auto-discovery and line buffering. |
| **C++ (Arduino / ESP32)**| Embedded Firmware | Physical Sensor & Actuator Driver | Real-time sensor polling (DHT22, Soil Analog, LDR) and digital relay triggering with JSON protocol. |

---

## 📦 Python Dependencies Breakdown (`requirements.txt`)

1. **`streamlit (>= 1.30.0)`**:
   - Renders live environmental telemetry gauges, status badges, and manual operator overrides.
   - Manages state across simulation steps and hardware reconnects.
2. **`plotly (>= 5.18.0)`**:
   - Generates responsive line charts and multi-axis visualizations for temperature, humidity, soil moisture, and light.
3. **`scikit-learn (>= 1.3.0)`**:
   - Trains and executes the offline Edge AI model classifying plant stress states:
     - `Healthy` (Optimal conditions)
     - `Water Stress` (Soil moisture depletion)
     - `Heat Stress` (Excessive temperature / high VPD)
     - `Low Light` (Insufficient photosynthetic irradiance)
4. **`pandas (>= 2.0.0)` & `numpy (>= 1.24.0)`**:
   - Structures telemetry logs into chronological data frames for rolling-window queries and tabular CSV downloads.
5. **`pyserial (>= 3.5)`**:
   - Scans system COM/TTY ports and streams JSON packets between Python and the microcontroller.
6. **`pytest (>= 7.4.0)`**:
   - Provides regression testing for sensor bounds, biophysical calculations, rule evaluations, and mock hardware.

---

## 💡 Edge AI vs. Traditional Cloud IoT

| Evaluation Parameter | Traditional Cloud IoT | Edge AI System (This Project) |
| :--- | :--- | :--- |
| **Internet Dependency** | 100% dependent on continuous internet | **100% Offline Capable** (Zero internet needed) |
| **Decision Latency** | 1,000 ms – 3,500 ms (network roundtrip) | **< 2 milliseconds** (in-memory execution) |
| **Operational Reliability** | Fails during rural network blackouts | **Uninterrupted 24/7 autonomous operation** |
| **Recurring Cost** | Monthly cloud API / server subscriptions | **₹0 Free & Open-Source** |
| **Data Sovereignty** | Sensor data sent to third-party servers | **100% Local Data Privacy** on the edge device |
| **Fail-Safe Operation** | Risk of actuator lockup on disconnect | **Deterministic Safety Watchdogs** in local code |

---

## 🌾 Biophysical Modeling: Vapor Pressure Deficit (VPD)

Rather than assessing air temperature and relative humidity in isolation, the edge engine calculates **Vapor Pressure Deficit (VPD)**, the agronomic standard for plant transpiration rate:

### Tetens Equation Formulation:

$$VP_{\text{sat}} = 0.61078 \times \exp\left(\frac{17.27 \times T}{T + 237.3}\right)$$

$$VP_{\text{air}} = VP_{\text{sat}} \times \left(\frac{RH}{100}\right)$$

$$VPD = VP_{\text{sat}} - VP_{\text{air}}$$

Where:
- $T$ = Ambient air temperature (°C)
- $RH$ = Relative humidity (%)
- $VP_{\text{sat}}$ = Saturation vapor pressure (kPa)
- $VP_{\text{air}}$ = Actual vapor pressure (kPa)
- $VPD$ = Vapor Pressure Deficit (kPa)

### Agronomic Decision Thresholds:
- **Optimal Range (0.80 to 1.20 kPa)**: Ideal stomatal conductance, nutrient uptake, and transpiration.
- **Low VPD (< 0.80 kPa)**: High humidity causes stagnant transpiration and elevates fungal/mildew risk.
- **High VPD (> 1.20 kPa)**: Dry air forces stomatal closure, causing water stress and wilting.

---

## 🛡️ Actuation Safety & Control Invariants

To safeguard real agricultural equipment (pumps and fans) from mechanical fatigue, the system enforces:
1. **Hysteresis Banding (Deadband Control)**:
   - Prevents high-frequency relay switching (relay chatter) around threshold boundaries (e.g., fan cooling has a $\pm 1.5^\circ\text{C}$ deadband).
2. **Runaway Irrigation Watchdog**:
   - Automatically shuts off the irrigation pump if it runs continuously for more than the maximum safe duration without soil moisture recovery (detects line leaks or sensor detachment).
3. **Global Emergency Stop**:
   - Instant software interlock disabling all relays (Pump, Fan, Grow Light) regardless of algorithmic recommendations.
