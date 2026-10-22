"""
app.py - Smart Greenhouse Automation Using Edge AI.
Streamlit Web Dashboard & Edge Orchestrator with Real Hardware & Simulation Support.
B.Tech CSE Minor Project - Babu Banarasi Das University, Lucknow.

Features:
- Dual Modes: Real Hardware (ESP32 / Arduino / RPi) & Digital Chamber Simulator
- Automatic Closed-Loop Control & Manual Operator Overrides
- Offline Edge AI: Agronomic Rules + Local Scikit-Learn ML + VPD Biophysics
- Live Alerts: Hardware connection loss, sensor failures, agronomic limits
- Persistent SQLite Database & Interactive Plotly Charts
- Strict Integrity: Never fakes simulated data as real hardware readings
"""

import time
import streamlit as st
import plotly.graph_objects as go
import pandas as pd
from datetime import datetime

# Import local project modules
from simulator import GreenhouseSimulator
from decision_engine import EdgeDecisionEngine, calculate_vpd
import hardware
import database

# 1. Page Configuration
st.set_page_config(page_title="Smart Greenhouse Edge AI", page_icon="🌿", layout="wide")

# Custom Green & Slate Theme CSS
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;600;700;800&display=swap');
    html, body, [class*="css"] { font-family: 'Plus Jakarta Sans', sans-serif; }
    .header-box {
        background: linear-gradient(135deg, #1b4332 0%, #2d6a4f 100%);
        color: white; padding: 1.2rem 1.6rem; border-radius: 12px; margin-bottom: 1.2rem;
    }
    .metric-card {
        background: white; border: 1px solid #e2e8f0; border-radius: 10px;
        padding: 1rem; box-shadow: 0 1px 3px rgba(0,0,0,0.05); margin-bottom: 0.5rem;
    }
    .status-on { background: #dcfce7; color: #166534; padding: 3px 8px; border-radius: 6px; font-weight: bold; }
    .status-off { background: #f1f5f9; color: #64748b; padding: 3px 8px; border-radius: 6px; font-weight: bold; }
    .status-hw-on { background: #dcfce7; color: #15803d; padding: 4px 10px; border-radius: 12px; font-weight: bold; font-size: 0.85rem; }
    .status-hw-off { background: #fee2e2; color: #b91c1c; padding: 4px 10px; border-radius: 12px; font-weight: bold; font-size: 0.85rem; }
    .status-sim { background: #fef3c7; color: #b45309; padding: 4px 10px; border-radius: 12px; font-weight: bold; font-size: 0.85rem; }
    .decision-box {
        background: #f8fafc; border-left: 4px solid #2d6a4f; border-radius: 6px;
        padding: 0.8rem 1rem; margin-bottom: 0.6rem;
    }
</style>
""", unsafe_allow_html=True)

# 2. Initialize Singletons in Streamlit Session State
if "simulator" not in st.session_state:
    st.session_state.simulator = GreenhouseSimulator()
    st.session_state.engine = EdgeDecisionEngine()
    st.session_state.hw_bridge = hardware.HardwareBridge()
    st.session_state.pump_on = False
    st.session_state.fan_on = False
    st.session_state.light_on = False
    st.session_state.mode = "AUTOMATIC"
    st.session_state.data_source = "SIMULATION"  # "SIMULATION" or "HARDWARE"
    st.session_state.emergency_stop = False
    st.session_state.hw_message = "Hardware interface initialized."
    st.session_state.last_reading = None

sim = st.session_state.simulator
engine = st.session_state.engine
hw = st.session_state.hw_bridge

# -------------------------------------------------------------
# SIDEBAR: DATA SOURCE & HARDWARE CONFIGURATION
# -------------------------------------------------------------
with st.sidebar:
    st.header("🎛️ System Configuration")
    
    # Data Source Selection
    source_choice = st.radio(
        "📡 Telemetry Data Source:",
        ["🧪 Simulation Twin (Chamber Model)", "🔌 Real Microcontroller Hardware (ESP32/Arduino)"],
        index=0 if st.session_state.data_source == "SIMULATION" else 1
    )
    new_source = "SIMULATION" if "Simulation" in source_choice else "HARDWARE"
    if new_source != st.session_state.data_source:
        st.session_state.data_source = new_source
        st.rerun()

    # Hardware Connection Settings
    if st.session_state.data_source == "HARDWARE":
        st.subheader("🔌 Microcontroller Serial Port")
        detected_ports = hardware.list_serial_ports()
        port_options = [p["device"] for p in detected_ports] + ["VIRTUAL_LOOPBACK"]
        
        selected_port = st.selectbox("Select COM/TTY Port:", options=port_options)
        baud_choice = st.selectbox("Baud Rate:", [115200, 9600, 57600], index=0)

        c_btn1, c_btn2 = st.columns(2)
        with c_btn1:
            if not hw.is_connected:
                if st.button("🟢 Connect", use_container_width=True):
                    if selected_port == "VIRTUAL_LOOPBACK":
                        ok, msg = hw.connect_virtual_loopback()
                    else:
                        ok, msg = hw.connect(selected_port, baud_choice)
                    st.session_state.hw_message = msg
                    database.log_event("HARDWARE", "CONNECT", msg)
                    st.rerun()
            else:
                if st.button("🔴 Disconnect", use_container_width=True):
                    hw.disconnect()
                    st.session_state.hw_message = "Hardware disconnected by operator."
                    database.log_event("HARDWARE", "DISCONNECT", "Operator disconnected hardware.")
                    st.rerun()
        with c_btn2:
            if st.button("🔄 Scan Ports", use_container_width=True):
                st.rerun()

        # Connection Status indicator in sidebar
        if hw.is_connected:
            badge_type = "status-hw-on"
            status_text = f"ONLINE: {hw.connected_port}"
        else:
            badge_type = "status-hw-off"
            status_text = "OFFLINE (Port Closed)"
        st.markdown(f"Status: <span class='{badge_type}'>{status_text}</span>", unsafe_allow_html=True)
        st.caption(f"Log: {st.session_state.hw_message}")

    # Configurable Thresholds Expander
    with st.expander("⚙️ Agronomic Thresholds & Safety Limits", expanded=False):
        st.write("Tune closed-loop autonomous setpoints:")
        engine.soil_min = st.slider("Soil Moisture Trigger (%):", 20.0, 60.0, float(engine.soil_min), 1.0)
        engine.temp_max = st.slider("Max Ventilation Temp (°C):", 22.0, 35.0, float(engine.temp_max), 0.5)
        engine.light_min = st.slider("Minimum Light Lux:", 5000.0, 30000.0, float(engine.light_min), 1000.0)

# -------------------------------------------------------------
# 3. TELEMETRY ACQUISITION & EXECUTION
# -------------------------------------------------------------
temp, humidity, soil, light = None, None, None, None
is_valid = False
hardware_error = None
current_source = "simulated"

if st.session_state.data_source == "HARDWARE":
    current_source = "hardware"
    if hw.is_connected:
        reading, is_valid, status_msg = hw.read_telemetry()
        if reading and is_valid:
            temp = reading["temperature"]
            humidity = reading["humidity"]
            soil = reading["soil_moisture"]
            light = reading["light_lux"]
            st.session_state.last_reading = reading
        else:
            is_valid = False
            hardware_error = status_msg
    else:
        is_valid = False
        hardware_error = "Real hardware not connected. Connect via USB Serial in the sidebar or switch to Simulation Twin."
else:
    # Simulation Twin step
    temp, humidity, soil, light, is_valid = sim.step(
        pump_active=st.session_state.pump_on,
        fan_active=st.session_state.fan_on,
        light_active=st.session_state.light_on
    )
    current_source = "simulated"

# Run Edge AI Decision Engine (Rules + Local ML)
decision = engine.evaluate(
    temp, humidity, soil, light,
    is_valid=is_valid,
    current_pump=st.session_state.pump_on,
    current_fan=st.session_state.fan_on
)

# Apply Autonomous Control if in AUTOMATIC mode & not in E-STOP
if st.session_state.mode == "AUTOMATIC" and not st.session_state.emergency_stop:
    st.session_state.pump_on = (decision["pump_action"] == "ON")
    st.session_state.fan_on = (decision["fan_action"] == "ON")
    st.session_state.light_on = (decision["light_action"] == "ON")

# If Real Hardware is connected, dispatch actuator relay states to ESP32/Arduino
if hw.is_connected:
    hw.send_actuators(
        pump=st.session_state.pump_on,
        fan=st.session_state.fan_on,
        light=st.session_state.light_on
    )

# Save valid reading to local SQLite database with source tag
if is_valid and temp is not None:
    database.save_reading(
        temp, humidity, soil, light,
        is_valid=True,
        scenario=sim.scenario if current_source == "simulated" else "LIVE_HARDWARE",
        source=current_source
    )

# -------------------------------------------------------------
# 4. HEADER BANNER
# -------------------------------------------------------------
if st.session_state.data_source == "HARDWARE":
    if hw.is_connected:
        source_badge = f"<span class='status-hw-on'>🟢 HARDWARE ONLINE ({hw.connected_port})</span>"
    else:
        source_badge = "<span class='status-hw-off'>🔴 HARDWARE OFFLINE</span>"
else:
    source_badge = "<span class='status-sim'>🟡 SIMULATION TWIN</span>"

st.markdown(f"""
<div class="header-box">
    <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap;">
        <div>
            <h2 style="margin:0; font-weight:800;">🌿 Smart Greenhouse Automation Using Edge AI</h2>
            <div style="color:#d8f3dc; font-size:0.9rem;">B.Tech CSE Minor Project · Babu Banarasi Das University, Lucknow</div>
        </div>
        <div style="margin-top: 5px;">
            <span style="background: rgba(255,255,255,0.2); padding: 5px 12px; border-radius: 20px; font-weight:600; font-size:0.85rem;">
                ⚡ MODE: {st.session_state.mode}
            </span>
            <span style="margin-left: 6px;">
                {source_badge}
            </span>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

# -------------------------------------------------------------
# 5. TAB LAYOUT
# -------------------------------------------------------------
tab1, tab2, tab3, tab4 = st.tabs([
    "🌿 Live Monitor & Controls",
    "🧠 Edge AI & Biophysics",
    "📊 Analytics & Data Export",
    "⚙️ System Diagnostics & Hardware Guide"
])

# -------------------------------------------------------------
# TAB 1: LIVE MONITOR & CONTROLS
# -------------------------------------------------------------
with tab1:
    # Row 1: Environmental Sensor Telemetry
    st.subheader("📡 Real-Time Environmental Telemetry")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Temperature", f"{temp} °C" if temp is not None else "N/A", f"Safe: 18°C – {engine.temp_max}°C")
    with c2:
        st.metric("Relative Humidity", f"{humidity} %" if humidity is not None else "N/A", "Optimal: 50% – 75%")
    with c3:
        st.metric("Soil Moisture", f"{soil} %" if soil is not None else "N/A", f"Trigger: < {engine.soil_min}%")
    with c4:
        st.metric("Light Intensity", f"{light:,.0f} lx" if light is not None else "N/A", f"Min: {engine.light_min:,.0f} lx")

    # Dynamic Alerts & Warnings (Requirement 6)
    alerts = []
    if st.session_state.data_source == "HARDWARE" and not hw.is_connected:
        alerts.append(("error", f"🚨 **HARDWARE CONNECTION WARNING:** {hardware_error}"))
    elif not is_valid:
        alerts.append(("error", f"🚨 **CRITICAL SENSOR FAULT:** {hardware_error or 'Telemetry invalid or probe disconnected. Actuators safely inhibited.'}"))
    else:
        if soil is not None and soil < engine.soil_min:
            alerts.append(("warning", f"⚠️ **SOIL MOISTURE WARNING:** Root zone moisture ({soil}%) is below safe minimum ({engine.soil_min}%). Irrigation pump active."))
        if temp is not None and temp > engine.temp_max:
            alerts.append(("warning", f"⚠️ **HIGH TEMPERATURE ALERT:** Ambient heat ({temp}°C) exceeds safe {engine.temp_max}°C threshold. Ventilation fan active."))
        elif temp is not None and temp < 18.0:
            alerts.append(("warning", f"⚠️ **LOW TEMPERATURE ALERT:** Temperature ({temp}°C) is below 18°C baseline."))
        if humidity is not None and humidity > 75.0:
            alerts.append(("warning", f"⚠️ **HIGH HUMIDITY WARNING:** Relative humidity ({humidity}%) exceeds 75% threshold. Risk of leaf mold/fungus."))
        if light is not None and light < engine.light_min:
            alerts.append(("info", f"ℹ️ **LOW LIGHT NOTICE:** Illumination ({light:,.0f} lx) below {engine.light_min:,.0f} lx. Grow lights active."))

    if alerts:
        for alert_type, alert_msg in alerts:
            if alert_type == "error":
                st.error(alert_msg)
            elif alert_type == "warning":
                st.warning(alert_msg)
            else:
                st.info(alert_msg)
    elif is_valid:
        st.success("✅ **CONDITIONS NOMINAL:** All environmental telemetry is within safe agronomic limits.")

    # Row 2: Equipment Status & Emergency Stop
    st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)
    e1, e2, e3, e4 = st.columns(4)
    with e1:
        badge = '<span class="status-on">● ACTIVE (ON)</span>' if st.session_state.pump_on else '<span class="status-off">○ STANDBY (OFF)</span>'
        st.markdown(f'<div class="metric-card"><strong>🚰 Drip Pump:</strong><br>{badge}</div>', unsafe_allow_html=True)
    with e2:
        badge = '<span class="status-on">● ACTIVE (ON)</span>' if st.session_state.fan_on else '<span class="status-off">○ STANDBY (OFF)</span>'
        st.markdown(f'<div class="metric-card"><strong>🌀 Exhaust Fan:</strong><br>{badge}</div>', unsafe_allow_html=True)
    with e3:
        badge = '<span class="status-on">● ACTIVE (ON)</span>' if st.session_state.light_on else '<span class="status-off">○ STANDBY (OFF)</span>'
        st.markdown(f'<div class="metric-card"><strong>💡 Grow Lights:</strong><br>{badge}</div>', unsafe_allow_html=True)
    with e4:
        if st.session_state.emergency_stop:
            if st.button("🟢 CLEAR E-STOP", type="primary", use_container_width=True):
                st.session_state.emergency_stop = False
                st.rerun()
        else:
            if st.button("🚨 EMERGENCY STOP", use_container_width=True):
                st.session_state.emergency_stop = True
                st.session_state.pump_on = False
                st.session_state.fan_on = False
                st.session_state.light_on = False
                if hw.is_connected:
                    hw.send_actuators(pump=False, fan=False, light=False)
                database.log_event("SAFETY", "E-STOP", "Operator activated Emergency Stop")
                st.rerun()

    st.markdown("<hr style='margin: 1rem 0;'>", unsafe_allow_html=True)

    # Simulation Scenarios OR Hardware Stream Controls
    col_scen, col_ctrl = st.columns([3, 2])
    with col_scen:
        if st.session_state.data_source == "SIMULATION":
            st.subheader("🧪 Teacher Demonstration Scenarios")
            scenarios = {
                "NORMAL": "🌱 Normal Balanced (24°C, 65% RH, 68% Soil, 25k Lux)",
                "DRY_SOIL": "🏜️ Dry Soil (Soil drops to 28% -> Triggers Pump)",
                "HIGH_TEMP": "🔥 High Temperature (Temp rises to 38°C -> Triggers Fan)",
                "LOW_LIGHT": "☁️ Low Light (Light drops to 2,800 Lux -> Triggers Grow Light)",
                "SENSOR_FAULT": "⚠️ Sensor Failure (Simulates broken wire -> Locks out safely)",
                "MANUAL": "🎛️ Manual Interactive Sliders"
            }
            chosen_scen = st.selectbox(
                "Select Scenario to Demonstrate:",
                options=list(scenarios.keys()),
                format_func=lambda x: scenarios[x]
            )
            if chosen_scen != sim.scenario:
                sim.set_scenario(chosen_scen)
                st.rerun()

            if chosen_scen == "MANUAL":
                m1, m2, m3, m4 = st.columns(4)
                sim.manual_temp = m1.slider("Temp (°C)", 10.0, 45.0, 24.0, 0.5)
                sim.manual_humidity = m2.slider("Humidity (%)", 20.0, 95.0, 65.0, 1.0)
                sim.manual_soil = m3.slider("Soil Moisture (%)", 10.0, 95.0, 68.0, 1.0)
                sim.manual_light = m4.slider("Light (Lux)", 1000, 50000, 25000, 500)
        else:
            st.subheader("🔌 Live Hardware Packet Inspector")
            if hw.is_connected and st.session_state.last_reading:
                st.json(st.session_state.last_reading)
            else:
                st.info("No physical packets received. Connect your ESP32 or select Virtual Loopback in the sidebar.")

    with col_ctrl:
        st.subheader("⚙️ Mode & Manual Overrides")
        mode = st.radio("Operating Mode:", ["AUTOMATIC", "MANUAL"], horizontal=True)
        if mode != st.session_state.mode:
            st.session_state.mode = mode
            database.log_event("SYSTEM", "MODE", f"Operating mode set to {mode}")
            st.rerun()

        if st.session_state.mode == "MANUAL":
            btn_col1, btn_col2 = st.columns(2)
            with btn_col1:
                if st.button("🚰 Toggle Pump", use_container_width=True):
                    st.session_state.pump_on = not st.session_state.pump_on
                    if hw.is_connected:
                        hw.send_actuators(st.session_state.pump_on, st.session_state.fan_on, st.session_state.light_on)
                    st.rerun()
                if st.button("🌀 Toggle Fan", use_container_width=True):
                    st.session_state.fan_on = not st.session_state.fan_on
                    if hw.is_connected:
                        hw.send_actuators(st.session_state.pump_on, st.session_state.fan_on, st.session_state.light_on)
                    st.rerun()
            with btn_col2:
                if st.button("💡 Toggle Lights", use_container_width=True):
                    st.session_state.light_on = not st.session_state.light_on
                    if hw.is_connected:
                        hw.send_actuators(st.session_state.pump_on, st.session_state.fan_on, st.session_state.light_on)
                    st.rerun()
                if st.button("🔄 Read Cycle", use_container_width=True):
                    st.rerun()
        else:
            btn_label = "🔄 Read Hardware Telemetry" if st.session_state.data_source == "HARDWARE" else "🔄 Step Simulation Cycle"
            if st.button(btn_label, type="primary", use_container_width=True):
                st.rerun()

    # Closed-Loop Reasoning Explanations
    st.markdown("<hr style='margin: 1rem 0;'>", unsafe_allow_html=True)
    st.subheader("📋 Closed-Loop Autonomous Reasoning")
    st.markdown(f'<div class="decision-box"><strong>🚰 Irrigation Decision:</strong> {decision["pump_reason"]}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="decision-box"><strong>🌀 Ventilation Decision:</strong> {decision["fan_reason"]}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="decision-box"><strong>💡 Lighting Decision:</strong> {decision["light_reason"]}</div>', unsafe_allow_html=True)

# -------------------------------------------------------------
# TAB 2: EDGE AI & BIOPHYSICS
# -------------------------------------------------------------
with tab2:
    st.subheader("🧠 Local Machine Learning & Agronomic Biophysics")
    st.markdown("Everything executes **100% offline on your laptop CPU** in < 2 milliseconds without cloud APIs.")

    ai_col1, ai_col2 = st.columns(2)
    with ai_col1:
        st.markdown(f"""
        <div class="metric-card">
            <h4>🌲 Scikit-Learn RandomForest Model</h4>
            <div style="font-size: 1.4rem; font-weight:800; color:#1b4332;">{decision['ml_prediction']}</div>
            <div style="color:#2d6a4f; font-weight:600;">Prediction Confidence: {decision['ml_confidence']}%</div>
            <p style="color:#64748b; font-size:0.85rem; margin-top:8px;">
                Trained locally on 1,500 synthetic agronomic samples adhering to FAO-56 standards.
                Evaluates microclimate patterns to forecast impending root water stress or fungal heat risk.
            </p>
        </div>
        """, unsafe_allow_html=True)

    with ai_col2:
        vpd = decision["vpd"]
        vpd_status = "Optimal Transpiration (0.8–1.2 kPa)" if 0.8 <= vpd <= 1.2 else ("High Water Stress (> 1.2 kPa)" if vpd > 1.2 else "Low Transpiration / Mold Risk (< 0.8 kPa)")
        st.markdown(f"""
        <div class="metric-card">
            <h4>🌾 Vapor Pressure Deficit (VPD)</h4>
            <div style="font-size: 1.4rem; font-weight:800; color:#1b4332;">{vpd:.2f} kPa</div>
            <div style="color:#166534; font-weight:600;">{vpd_status}</div>
            <p style="color:#64748b; font-size:0.85rem; margin-top:8px;">
                Calculated via the <strong>Tetens Equation</strong>. VPD measures the drying power of air.
                High VPD causes plants to close stomata and stop growing; low VPD halts transpiration.
            </p>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("### 🔍 Dual-Engine Decision Architecture")
    st.info("""
    - **Strategy A (Deterministic Rules Engine):** Enforces hard agronomic safety bounds (e.g. soil < 45% -> Pump ON; temp > 28°C -> Fan ON; sensor broken -> Stop).
    - **Strategy B (Local Scikit-Learn Model):** Evaluates multi-channel relationships to predict crop stress early.
    - **Safety Guarantee:** Machine Learning predictions serve as an advisory layer; they can never override or bypass physical safety limits.
    """)

# -------------------------------------------------------------
# TAB 3: ANALYTICS & DATA EXPORT
# -------------------------------------------------------------
with tab3:
    st.subheader("📈 Environmental History (SQLite Persistent Storage)")
    df_hist = database.get_recent_readings(limit=60)

    if not df_hist.empty and len(df_hist) >= 2:
        # Plotly Time-Series Chart
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=df_hist['timestamp'], y=df_hist['temperature'], name='Temp (°C)', line=dict(color='#ef4444', width=2)))
        fig.add_trace(go.Scatter(x=df_hist['timestamp'], y=df_hist['humidity'], name='Humidity (%)', line=dict(color='#0284c7', width=2)))
        fig.add_trace(go.Scatter(x=df_hist['timestamp'], y=df_hist['soil_moisture'], name='Soil (%)', line=dict(color='#16a34a', width=2.5)))
        fig.update_layout(height=320, margin=dict(l=20, r=20, t=30, b=20), legend=dict(orientation="h", y=1.1))
        st.plotly_chart(fig, use_container_width=True)

        # CSV Download Button
        csv_bytes = df_hist.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Download Telemetry CSV",
            data=csv_bytes,
            file_name=f"greenhouse_telemetry_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv",
            type="primary"
        )
    else:
        st.info("Collecting initial sensor readings... Historical trend chart will appear after a few cycles.")

    # Recent Telemetry Table with Source Attribution
    if not df_hist.empty:
        st.subheader("📊 Recent Telemetry Log (Source Tagged)")
        display_df = df_hist[['timestamp', 'temperature', 'humidity', 'soil_moisture', 'light_lux', 'scenario', 'source']].head(15)
        st.dataframe(display_df, use_container_width=True, hide_index=True)

    # Recent Event Log
    st.subheader("📋 Recent Automation Events")
    events = database.get_recent_events(limit=10)
    if events:
        st.dataframe(pd.DataFrame(events), use_container_width=True, hide_index=True)

# -------------------------------------------------------------
# TAB 4: SYSTEM DIAGNOSTICS & HARDWARE GUIDE
# -------------------------------------------------------------
with tab4:
    st.subheader("⚙️ System Demonstration & Verification Workflow")
    st.markdown("""
    **Step 1:** Select **`🏜️ Dry Soil`** scenario in Tab 1. Click **Step Cycle**.
    - *Observation:* Soil moisture drops to 28%, and the **Irrigation Pump switches to ACTIVE (ON)**.
    - *Behavior:* As the pump stays on, soil moisture climbs back to 70% and automatically shuts off.

    **Step 2:** Select **`🔥 High Temperature`** scenario. Click **Step Cycle**.
    - *Observation:* Temperature rises to 38°C, and the **Exhaust Fan switches to ACTIVE (ON)**.
    - *Behavior:* Fan uses hysteresis (±1.5°C deadband) to prevent rapid relay chatter.

    **Step 3:** Select **`⚠️ Sensor Failure`** scenario. Click **Step Cycle**.
    - *Observation:* System detects invalid data and safely **locks all actuators OFF**.

    **Step 4:** Open **Tab 2 (Edge AI & Biophysics)**.
    - *Observation:* Local Scikit-Learn RandomForest prediction and VPD formula executing 100% offline.
    """)

    st.markdown("### 🔌 Real Hardware Setup & Wiring Pinout")
    st.markdown("""
    When connecting to physical hardware, flash `esp32_greenhouse.ino` using the Arduino IDE:
    
    | Component | ESP32 Pin | Purpose |
    |---|---|---|
    | **DHT22 Sensor** | GPIO 4 | Ambient Temperature & Humidity |
    | **Capacitive Soil Probe v1.2** | GPIO 34 (ADC1) | Analog Soil Moisture Measurement |
    | **LDR / BH1750 Light Sensor** | GPIO 35 (ADC1) | Solar Illumination (Lux) |
    | **Relay 1 (Water Pump)** | GPIO 16 | 12V Submersible Drip Pump |
    | **Relay 2 (Exhaust Fan)** | GPIO 17 | 12V Ventilation Fan |
    | **Relay 3 (Grow Lights)** | GPIO 18 | Full-Spectrum LED Grow Lights |
    """)

    st.markdown("### ❓ Technical Architecture Questions & Deep Dive")
    with st.expander("1. Why is Edge AI superior to Cloud IoT for agricultural automation?"):
        st.write("Cloud IoT requires constant internet connectivity. If the connection drops in rural farms, actuators may fail or pumps could run indefinitely. Edge AI makes all decisions locally in < 2 ms with zero recurring costs and complete fault tolerance.")
    with st.expander("2. What is Vapor Pressure Deficit (VPD) and why is it used?"):
        st.write("VPD measures the actual drying power of air on plant leaves using the Tetens equation. The optimal range is 0.8–1.2 kPa. High VPD forces stomata to close and causes wilting, while low VPD prevents transpiration and invites fungal rot.")
    with st.expander("3. How does the application prevent simulated data from leaking into real hardware mode?"):
        st.write("The system features a strict source selector. When Real Hardware mode is selected, data is only accepted via physical serial packets. If the board is unplugged, the system raises an explicit hardware disconnection alert.")
    with st.expander("4. Why use SQLite instead of MySQL or MongoDB?"):
        st.write("SQLite is zero-configuration and serverless, embedded directly into Python on edge devices like Raspberry Pi, eliminating database daemon failure points.")
    with st.expander("5. What is the role of the Machine Learning model?"):
        st.write("It evaluates multi-variable conditions to classify crop stress states, while rule thresholds enforce hard safety limits.")
