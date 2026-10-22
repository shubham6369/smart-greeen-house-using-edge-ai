"""
decision_engine.py - Edge AI Brain for Smart Greenhouse.
Combines deterministic agronomic threshold rules with a lightweight local
Scikit-Learn Machine Learning classifier and dynamic VPD computation.
Easy to explain to your teacher: Rules ensure safety; ML forecasts crop stress!
"""

import math
import numpy as np
import pandas as pd
from pathlib import Path
from sklearn.ensemble import RandomForestClassifier
import joblib

# Paths for offline model storage
MODEL_FILE = Path(__file__).resolve().parent / "data" / "model.joblib"

def calculate_vpd(temperature, humidity):
    """
    Calculate Vapor Pressure Deficit (VPD in kPa) using the Tetens Equation.
    Measures the atmospheric drying power driving plant transpiration.
    Optimal greenhouse range is 0.8 to 1.2 kPa.
    """
    if temperature is None or humidity is None:
        return 1.0
    # Saturated Vapor Pressure in kPa
    vp_sat = 0.61078 * math.exp((17.27 * temperature) / (temperature + 237.3))
    # Actual Vapor Pressure in kPa
    vp_air = vp_sat * (max(0.0, min(100.0, humidity)) / 100.0)
    return round(max(0.0, vp_sat - vp_air), 2)

class EdgeDecisionEngine:
    """Evaluates rules and runs local Scikit-Learn inference."""

    def __init__(self):
        # Configurable agronomic thresholds (Tomato default)
        self.soil_min = 45.0
        self.soil_target = 70.0
        self.temp_max = 28.0
        self.fan_hysteresis = 1.5
        self.light_min = 15000.0

        # Load or train local ML model
        self.model = self._load_or_train_model()

    def _load_or_train_model(self):
        """Load trained model or train a fast 50-tree RandomForest locally."""
        if MODEL_FILE.exists():
            try:
                return joblib.load(str(MODEL_FILE))
            except Exception:
                pass

        # Train lightweight model on synthetic agronomic dataset (FAO-56 guidelines)
        np.random.seed(42)
        samples = []
        labels = []
        for _ in range(1500):
            t = np.random.uniform(15.0, 40.0)
            h = np.random.uniform(30.0, 95.0)
            s = np.random.uniform(20.0, 90.0)
            l = np.random.uniform(2000.0, 50000.0)
            v = calculate_vpd(t, h)

            # Ground truth agronomic labels
            if s < 45.0 and t > 28.0:
                label = "Water & Heat Stress"
            elif s < 45.0:
                label = "Water Stress (Irrigate)"
            elif t > 28.0 or h > 80.0:
                label = "Heat/Humidity Stress (Ventilate)"
            elif l < 15000.0:
                label = "Low Light (Grow Lights)"
            else:
                label = "Nominal / Healthy"

            samples.append([t, h, s, l, v])
            labels.append(label)

        clf = RandomForestClassifier(n_estimators=30, max_depth=6, random_state=42)
        X = pd.DataFrame(samples, columns=["temp", "humidity", "soil", "light", "vpd"])
        clf.fit(X, labels)

        MODEL_FILE.parent.mkdir(exist_ok=True)
        joblib.dump(clf, str(MODEL_FILE))
        return clf

    def evaluate(self, temp, humidity, soil, light, is_valid=True, current_pump=False, current_fan=False):
        """
        Evaluate environmental conditions using Rules + Local ML.
        Returns recommendations and human-readable explanations.
        """
        # Safety Lockout: If sensor reading is broken or invalid, inhibit all triggers
        if not is_valid or temp is None or humidity is None or soil is None or light is None:
            return {
                "pump_action": "OFF",
                "fan_action": "OFF",
                "light_action": "OFF",
                "pump_reason": "SAFETY INHIBIT: Sensor reading is invalid or probe disconnected.",
                "fan_reason": "SAFETY INHIBIT: Sensor reading is invalid or probe disconnected.",
                "light_reason": "SAFETY INHIBIT: Sensor reading is invalid or probe disconnected.",
                "vpd": 1.0,
                "ml_prediction": "Sensor Fault Detected",
                "ml_confidence": 100.0,
                "is_safe": False
            }

        vpd = calculate_vpd(temp, humidity)

        # 1. Irrigation Rule
        if soil < self.soil_min:
            pump_action = "ON"
            pump_reason = f"Irrigation ON: Soil moisture ({soil}%) is below minimum limit ({self.soil_min}%)."
        elif soil >= self.soil_target:
            pump_action = "OFF"
            pump_reason = f"Irrigation OFF: Soil moisture ({soil}%) has reached target ({self.soil_target}%)."
        else:
            pump_action = "ON" if current_pump else "OFF"
            pump_reason = f"Irrigation buffer: Soil moisture ({soil}%) is in acceptable range ({self.soil_min}% – {self.soil_target}%)."

        # 2. Climate Ventilation Rule (with hysteresis)
        if temp > self.temp_max:
            fan_action = "ON"
            fan_reason = f"Ventilation ON: Temperature ({temp}°C) exceeds max threshold ({self.temp_max}°C)."
        elif temp < (self.temp_max - self.fan_hysteresis):
            fan_action = "OFF"
            fan_reason = f"Ventilation OFF: Temperature ({temp}°C) cooled safely below hysteresis band."
        else:
            fan_action = "ON" if current_fan else "OFF"
            fan_reason = f"Ventilation in deadband ({temp}°C)."

        # 3. Supplemental Lighting Rule
        if light < self.light_min:
            light_action = "ON"
            light_reason = f"Grow Light ON: Ambient light ({light:,.0f} lx) is below photoperiod target ({self.light_min:,.0f} lx)."
        else:
            light_action = "OFF"
            light_reason = f"Grow Light OFF: Sunlight ({light:,.0f} lx) is sufficient."

        # 4. Local Machine Learning Inference
        X_live = pd.DataFrame([[temp, humidity, soil, light, vpd]], columns=["temp", "humidity", "soil", "light", "vpd"])
        ml_pred = self.model.predict(X_live)[0]
        probs = self.model.predict_proba(X_live)[0]
        confidence = round(float(np.max(probs)) * 100, 1)

        return {
            "pump_action": pump_action,
            "fan_action": fan_action,
            "light_action": light_action,
            "pump_reason": pump_reason,
            "fan_reason": fan_reason,
            "light_reason": light_reason,
            "vpd": vpd,
            "ml_prediction": ml_pred,
            "ml_confidence": confidence,
            "is_safe": True
        }
