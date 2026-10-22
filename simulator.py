"""
simulator.py - Digital Twin Microclimate Simulator for Smart Greenhouse.
Simulates environmental physics and realistic closed-loop actuator feedback.
Easy to explain to your teacher: simple Python variables that change over time.
"""

import random

class GreenhouseSimulator:
    """Simulates temperature, humidity, soil moisture, and light with closed-loop feedback."""

    def __init__(self):
        # Environmental state variables
        self.temperature = 24.2
        self.humidity = 64.0
        self.soil_moisture = 68.0
        self.light_lux = 25000.0

        # Scenario control
        self.scenario = "NORMAL"

        # Manual sliders (when in MANUAL scenario)
        self.manual_temp = 24.0
        self.manual_humidity = 65.0
        self.manual_soil = 68.0
        self.manual_light = 25000.0

    def set_scenario(self, scenario_name):
        """Inject preset agronomic scenarios for teacher demonstrations."""
        self.scenario = scenario_name.upper()
        if self.scenario == "DRY_SOIL":
            self.soil_moisture = 28.0  # Below 45% trigger -> causes irrigation
        elif self.scenario == "HIGH_TEMP":
            self.temperature = 37.5    # Above 28°C trigger -> causes ventilation
        elif self.scenario == "LOW_LIGHT":
            self.light_lux = 2800.0    # Below 15,000 lx trigger -> causes grow light
        elif self.scenario == "NORMAL":
            self.temperature = 24.2
            self.humidity = 64.0
            self.soil_moisture = 68.0
            self.light_lux = 25000.0

    def step(self, pump_active=False, fan_active=False, light_active=False):
        """
        Advance one simulation cycle with closed-loop actuator effects.
        Returns (temp, humidity, soil_moisture, light_lux, is_valid).
        """
        if self.scenario == "SENSOR_FAULT":
            # Simulate a broken sensor or ADC disconnect to demonstrate safety inhibit
            return -99.9, None, 150.0, None, False

        if self.scenario == "MANUAL":
            # Direct tracking of manual slider values
            self.temperature = float(self.manual_temp)
            self.humidity = float(self.manual_humidity)
            self.soil_moisture = float(self.manual_soil)
            self.light_lux = float(self.manual_light)
        else:
            # Add minor natural fluctuations
            noise_t = random.uniform(-0.15, 0.15)
            noise_h = random.uniform(-0.3, 0.3)
            noise_s = random.uniform(-0.05, 0.05)
            noise_l = random.uniform(-150, 150)

            # Natural slow decay in soil moisture (evapotranspiration)
            self.soil_moisture = max(15.0, self.soil_moisture - 0.08 + noise_s)
            self.temperature = max(15.0, min(45.0, self.temperature + noise_t))
            self.humidity = max(20.0, min(95.0, self.humidity + noise_h))
            self.light_lux = max(1000.0, min(80000.0, self.light_lux + noise_l))

        # Closed-loop actuator physics:
        # 1. Active pump delivers water to soil
        if pump_active:
            self.soil_moisture = min(92.0, self.soil_moisture + 2.5)

        # 2. Active fan exhausts hot humid air
        if fan_active:
            self.temperature = max(18.0, self.temperature - 0.7)
            self.humidity = max(40.0, self.humidity - 0.9)

        # 3. Active grow light supplements solar lux
        if light_active:
            self.light_lux = min(75000.0, self.light_lux + 12000.0)

        # Validate plausible limits
        is_valid = (
            -10.0 <= self.temperature <= 65.0 and
            0.0 <= self.humidity <= 100.0 and
            0.0 <= self.soil_moisture <= 100.0 and
            0.0 <= self.light_lux <= 100000.0
        )

        return (
            round(self.temperature, 1),
            round(self.humidity, 1),
            round(self.soil_moisture, 1),
            round(self.light_lux, 0),
            is_valid
        )
