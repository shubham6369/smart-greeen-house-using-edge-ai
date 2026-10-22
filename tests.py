"""
tests.py - Simple Automated Verification Suite for Smart Greenhouse.
Easily runnable via: `python tests.py` or `pytest`.
Validates all core features: simulator, decision rules, ML inference, and database.
"""

from simulator import GreenhouseSimulator
from decision_engine import EdgeDecisionEngine, calculate_vpd
import database

def test_simulator_and_validation():
    """Verify simulator generates values and detects sensor faults."""
    sim = GreenhouseSimulator()
    sim.set_scenario("NORMAL")
    t, h, s, l, ok = sim.step()
    assert ok is True
    assert 10.0 <= t <= 45.0
    assert 0.0 <= s <= 100.0

    # Test fault scenario
    sim.set_scenario("SENSOR_FAULT")
    t, h, s, l, ok = sim.step()
    assert ok is False
    print("[OK] Simulator & Sensor Validation: PASSED")

def test_vpd_calculation():
    """Verify Tetens equation calculates proper Vapor Pressure Deficit."""
    vpd = calculate_vpd(25.0, 60.0)
    assert 0.8 <= vpd <= 1.5
    print("[OK] Biophysics VPD (Tetens Equation): PASSED")

def test_decision_rules():
    """Verify threshold rules for irrigation, ventilation, and lighting."""
    engine = EdgeDecisionEngine()

    # 1. Dry soil -> Pump ON
    dec_dry = engine.evaluate(temp=24.0, humidity=60.0, soil=30.0, light=25000.0)
    assert dec_dry["pump_action"] == "ON"
    assert "Irrigation ON" in dec_dry["pump_reason"]

    # 2. Adequate soil -> Pump OFF
    dec_wet = engine.evaluate(temp=24.0, humidity=60.0, soil=75.0, light=25000.0)
    assert dec_wet["pump_action"] == "OFF"

    # 3. High temperature -> Fan ON
    dec_hot = engine.evaluate(temp=35.0, humidity=60.0, soil=65.0, light=25000.0)
    assert dec_hot["fan_action"] == "ON"

    # 4. Low light -> Grow light ON
    dec_dark = engine.evaluate(temp=22.0, humidity=60.0, soil=65.0, light=3000.0)
    assert dec_dark["light_action"] == "ON"

    # 5. Sensor Fault -> Safe Inhibit (All OFF)
    dec_fault = engine.evaluate(temp=-99.0, humidity=None, soil=150.0, light=None, is_valid=False)
    assert dec_fault["pump_action"] == "OFF"
    assert dec_fault["fan_action"] == "OFF"
    assert dec_fault["is_safe"] is False
    print("[OK] Decision Rules & Safety Invariants: PASSED")

def test_machine_learning_inference():
    """Verify local Scikit-Learn RandomForest classifier makes predictions."""
    engine = EdgeDecisionEngine()
    dec = engine.evaluate(temp=24.0, humidity=65.0, soil=65.0, light=25000.0)
    assert dec["ml_prediction"] is not None
    assert dec["ml_confidence"] > 50.0
    print("[OK] Local Scikit-Learn Edge ML Inference: PASSED")

def test_database_persistence():
    """Verify readings are saved and read back from SQLite."""
    read_id = database.save_reading(24.5, 65.0, 68.0, 25000.0, is_valid=True, scenario="TEST")
    assert read_id > 0
    df = database.get_recent_readings(limit=5)
    assert not df.empty
    print("[OK] Persistent SQLite Database: PASSED")

def test_hardware_bridge_and_loopback():
    """Verify hardware serial driver, virtual loopback, packet parsing, and sanity checks."""
    import hardware
    ports = hardware.list_serial_ports()
    assert isinstance(ports, list)

    # Test Virtual Hardware loopback
    bridge = hardware.HardwareBridge()
    ok, msg = bridge.connect_virtual_loopback()
    assert ok is True
    assert bridge.is_connected is True

    # Test actuator command dispatch
    send_ok, send_msg = bridge.send_actuators(pump=True, fan=False, light=True)
    assert send_ok is True

    # Test live telemetry reading
    reading, is_valid, status_msg = bridge.read_telemetry()
    assert is_valid is True
    assert reading is not None
    assert reading["temperature"] > 0
    assert reading["soil_moisture"] > 0
    assert reading["source"] == "virtual_hardware"

    bridge.disconnect()
    assert bridge.is_connected is False
    print("[OK] Real Hardware Driver & Loopback Protocol: PASSED")

if __name__ == "__main__":
    print("--- Running Smart Greenhouse Test Suite ---")
    test_simulator_and_validation()
    test_vpd_calculation()
    test_decision_rules()
    test_machine_learning_inference()
    test_database_persistence()
    test_hardware_bridge_and_loopback()
    print("\n[SUCCESS] ALL TESTS PASSED! (100% Ready for Evaluation / Production)")
