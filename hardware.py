"""
hardware.py - Real Hardware Interface for Smart Greenhouse.
Connects Python to an ESP32, Arduino, or Raspberry Pi over USB-Serial / UART.
Reads live DHT22, soil moisture, and light sensors, and dispatches relay actuation commands.
Never fakes hardware: reports explicit connection status, errors, and port telemetry.
"""

import json
import time
import io
import logging
from typing import Optional, Dict, Any, Tuple, List

try:
    import serial
    import serial.tools.list_ports
    HAS_SERIAL = True
except ImportError:
    HAS_SERIAL = False

logger = logging.getLogger("GreenhouseHardware")

def list_serial_ports() -> List[Dict[str, str]]:
    """Scan and return all active COM/TTY serial ports on Windows, Linux, or macOS."""
    if not HAS_SERIAL:
        return []
    ports = []
    try:
        for p in serial.tools.list_ports.comports():
            ports.append({
                "device": p.device,
                "description": p.description or p.device,
                "hwid": p.hwid or ""
            })
    except Exception as e:
        logger.error(f"Failed to scan serial ports: {e}")
    return ports


class VirtualSerialDevice:
    """
    Virtual serial port loopback emulator for hardware protocol testing.
    Mirrors the exact Arduino/ESP32 firmware packet exchange over an in-memory stream.
    Used for testing hardware drivers when no physical board is plugged into USB.
    """
    def __init__(self):
        self.is_open = True
        self.pump_state = 0
        self.fan_state = 0
        self.light_state = 0
        self.buffer = ""

    def write(self, data: bytes):
        text = data.decode('utf-8', errors='ignore')
        try:
            parsed = json.loads(text.strip())
            if parsed.get("cmd") == "ACTUATE":
                self.pump_state = parsed.get("pump", 0)
                self.fan_state = parsed.get("fan", 0)
                self.light_state = parsed.get("light", 0)
        except Exception:
            pass

    def readline(self) -> bytes:
        # Generate framed JSON packet matching esp32_greenhouse.ino
        telemetry = {
            "temperature": round(24.5 + (1.2 if self.fan_state else 0.0), 2),
            "humidity": round(65.0 - (5.0 if self.fan_state else 0.0), 2),
            "soil_moisture": round(52.0 + (10.0 if self.pump_state else 0.0), 2),
            "light_lux": round(450.0 + (300.0 if self.light_state else 0.0), 1)
        }
        return (json.dumps(telemetry) + "\n").encode('utf-8')

    def reset_input_buffer(self):
        pass

    def reset_output_buffer(self):
        pass

    def flush(self):
        pass

    def close(self):
        self.is_open = False


class HardwareBridge:
    """
    Manages USB-Serial communication with microcontroller (ESP32/Arduino/Raspberry Pi).
    Implements bidirectional JSON packet exchange:
      - Reads live sensor stream: {"temperature": 24.5, "humidity": 65.0, "soil_moisture": 52.0, "light_lux": 450.0}
      - Sends relay actuation commands: {"cmd": "ACTUATE", "pump": 1, "fan": 0, "light": 0}
    """
    def __init__(self):
        self.ser: Optional[Any] = None
        self.connected_port: Optional[str] = None
        self.baudrate: int = 115200
        self.is_connected: bool = False
        self.is_virtual: bool = False
        self.last_error: Optional[str] = None
        self.last_reading: Optional[Dict[str, Any]] = None
        self.last_read_time: float = 0.0

    def connect(self, port: str, baudrate: int = 115200, timeout: float = 2.0) -> Tuple[bool, str]:
        """Establish serial connection to specified physical COM port."""
        if not HAS_SERIAL:
            self.last_error = "pyserial library is not installed."
            return False, self.last_error

        if self.is_connected:
            self.disconnect()

        try:
            self.ser = serial.Serial(
                port=port,
                baudrate=baudrate,
                timeout=timeout,
                write_timeout=timeout
            )
            time.sleep(1.5)  # Allow board reboot on DTR toggle
            self.ser.reset_input_buffer()
            self.ser.reset_output_buffer()
            self.connected_port = port
            self.baudrate = baudrate
            self.is_connected = True
            self.is_virtual = False
            self.last_error = None
            return True, f"Successfully connected to hardware on {port} at {baudrate} baud."
        except Exception as e:
            self.is_connected = False
            self.ser = None
            self.connected_port = None
            self.last_error = str(e)
            return False, f"Failed to open port {port}: {e}"

    def connect_virtual_loopback(self) -> Tuple[bool, str]:
        """Connect to in-memory virtual microcontroller loopback for testing hardware protocol."""
        if self.is_connected:
            self.disconnect()
        self.ser = VirtualSerialDevice()
        self.connected_port = "VIRTUAL_LOOPBACK"
        self.baudrate = 115200
        self.is_connected = True
        self.is_virtual = True
        self.last_error = None
        return True, "Connected to Virtual Hardware Loopback device (Testing Driver)."

    def disconnect(self) -> None:
        """Safely close serial port and reset state."""
        if self.ser and getattr(self.ser, "is_open", False):
            try:
                self.send_actuators(pump=False, fan=False, light=False)
                self.ser.close()
            except Exception:
                pass
        self.ser = None
        self.is_connected = False
        self.is_virtual = False
        self.connected_port = None

    def read_telemetry(self) -> Tuple[Optional[Dict[str, Any]], bool, str]:
        """
        Read one line of JSON telemetry from the physical microcontroller.
        Returns: (reading_dict, is_valid, message)
        """
        if not self.is_connected or not self.ser or not getattr(self.ser, "is_open", False):
            return None, False, "Hardware not connected (Port closed)."

        try:
            raw_line = self.ser.readline().decode('utf-8', errors='ignore').strip()
            if not raw_line:
                return None, False, "Serial read timeout: No data received from microcontroller."

            try:
                data = json.loads(raw_line)
            except json.JSONDecodeError:
                parts = raw_line.split(",")
                if len(parts) >= 4:
                    try:
                        data = {
                            "temperature": float(parts[0]),
                            "humidity": float(parts[1]),
                            "soil_moisture": float(parts[2]),
                            "light_lux": float(parts[3])
                        }
                    except ValueError:
                        return None, False, f"Corrupted packet received: '{raw_line}'"
                else:
                    return None, False, f"Malformed packet: '{raw_line}'"

            t = float(data.get("temperature", 0.0))
            h = float(data.get("humidity", 0.0))
            s = float(data.get("soil_moisture", 0.0))
            l = float(data.get("light_lux", 0.0))

            # Hardware sanity checking (detect sensor open-circuit / disconnection)
            is_valid = True
            fault_msgs = []

            if t < -20.0 or t > 70.0 or t == -127.0:
                is_valid = False
                fault_msgs.append("DHT sensor disconnected or open-circuit (Invalid Temp)")
            if h < 0.0 or h > 100.0:
                is_valid = False
                fault_msgs.append("Humidity sensor out of physical range (0-100%)")
            if s < 0.0 or s > 100.0:
                is_valid = False
                fault_msgs.append("Soil moisture ADC probe out of bounds")
            if l < 0.0:
                is_valid = False
                fault_msgs.append("Light sensor lux cannot be negative")

            status_msg = "Live hardware reading valid." if is_valid else "; ".join(fault_msgs)

            reading = {
                "temperature": round(t, 2),
                "humidity": round(h, 2),
                "soil_moisture": round(s, 2),
                "light_lux": round(l, 1),
                "is_valid": is_valid,
                "status_message": status_msg,
                "source": "hardware" if not self.is_virtual else "virtual_hardware",
                "port": self.connected_port,
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
            }

            self.last_reading = reading
            self.last_read_time = time.time()
            return reading, is_valid, status_msg

        except Exception as e:
            self.last_error = f"Serial read error: {e}"
            return None, False, self.last_error

    def send_actuators(self, pump: bool, fan: bool, light: bool) -> Tuple[bool, str]:
        """
        Send relay actuator commands to physical microcontroller over Serial.
        Packet format: {"cmd": "ACTUATE", "pump": 1, "fan": 0, "light": 0}\\n
        """
        if not self.is_connected or not self.ser or not getattr(self.ser, "is_open", False):
            return False, "Cannot send command: Hardware is not connected."

        payload = {
            "cmd": "ACTUATE",
            "pump": 1 if pump else 0,
            "fan": 1 if fan else 0,
            "light": 1 if light else 0
        }
        try:
            cmd_bytes = (json.dumps(payload) + "\n").encode('utf-8')
            self.ser.write(cmd_bytes)
            if hasattr(self.ser, "flush"):
                self.ser.flush()
            return True, f"Hardware command dispatched: PUMP={payload['pump']}, FAN={payload['fan']}, LIGHT={payload['light']}"
        except Exception as e:
            self.last_error = f"Failed to send actuator command: {e}"
            return False, self.last_error
