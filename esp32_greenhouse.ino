/*
  ========================================================================
  SMART GREENHOUSE AUTOMATION USING EDGE AI
  ESP32 / Arduino Hardware Firmware (Ready-to-Flash)
  ========================================================================
  B.Tech Minor Project - Babu Banarasi Das University, Lucknow
  
  Wiring Pinout:
  - DHT22 (Temperature & Humidity): GPIO 4 (10k pull-up resistor to 3.3V)
  - Capacitive Soil Moisture Sensor: GPIO 34 (Analog ADC1)
  - Light Sensor (LDR Divider / BH1750): GPIO 35 (Analog ADC1)
  - Relay 1 (Water Pump): GPIO 16 (Active LOW/HIGH)
  - Relay 2 (Ventilation Fan): GPIO 17
  - Relay 3 (Grow Lights): GPIO 18

  Serial Protocol (115200 Baud):
  - Transmits JSON telemetry to Python:
    {"temperature": 24.5, "humidity": 65.2, "soil_moisture": 58.1, "light_lux": 620.0}
  - Receives JSON commands from Python:
    {"cmd": "ACTUATE", "pump": 1, "fan": 0, "light": 0}
*/

#include <Arduino.h>

// If using Adafruit DHT Library, uncomment below:
// #include "DHT.h"
// #define DHTPIN 4
// #define DHTTYPE DHT22
// DHT dht(DHTPIN, DHTTYPE);

// Pin Definitions
const int PIN_DHT = 4;
const int PIN_SOIL = 34;
const int PIN_LDR = 35;

const int RELAY_PUMP = 16;
const int RELAY_FAN = 17;
const int RELAY_LIGHT = 18;

// Set to true if your relay module is Active-LOW (most 5V relay modules are Active LOW)
const bool RELAY_ACTIVE_LOW = true;

// Timing
unsigned long lastTelemetryTime = 0;
const unsigned long TELEMETRY_INTERVAL = 2000; // Send reading every 2 seconds

void setRelay(int pin, bool state) {
  if (RELAY_ACTIVE_LOW) {
    digitalWrite(pin, state ? LOW : HIGH);
  } else {
    digitalWrite(pin, state ? HIGH : LOW);
  }
}

void setup() {
  Serial.begin(115200);
  delay(1000);

  // Setup Relays
  pinMode(RELAY_PUMP, OUTPUT);
  pinMode(RELAY_FAN, OUTPUT);
  pinMode(RELAY_LIGHT, OUTPUT);

  // Turn off all actuators at boot
  setRelay(RELAY_PUMP, false);
  setRelay(RELAY_FAN, false);
  setRelay(RELAY_LIGHT, false);

  // Setup Analog Inputs
  pinMode(PIN_SOIL, INPUT);
  pinMode(PIN_LDR, INPUT);

  // dht.begin();
  // Serial.println("{\"status\": \"ESP32 Greenhouse Firmware Initialized\"}");
}

// Convert ADC reading (0 - 4095) to Soil Moisture Percentage (0 - 100%)
float readSoilMoisture() {
  int raw = analogRead(PIN_SOIL);
  // Typical capacitive sensor: Air (dry) ~ 3200, Water (wet) ~ 1400
  int dryValue = 3200;
  int wetValue = 1400;
  float moisture = map(raw, dryValue, wetValue, 0, 100);
  if (moisture < 0) moisture = 0.0;
  if (moisture > 100) moisture = 100.0;
  return moisture;
}

// Convert ADC reading to Approximate Light Lux (0 - 2000 Lux)
float readLightLux() {
  int raw = analogRead(PIN_LDR);
  // Higher resistance in dark -> lower voltage -> map to Lux
  float lux = map(raw, 0, 4095, 0, 2000);
  if (lux < 0) lux = 0.0;
  return lux;
}

// Read or simulate DHT values if library is not installed
void readDHT(float &temp, float &hum) {
  // If using DHT library:
  // temp = dht.readTemperature();
  // hum = dht.readHumidity();
  // if (isnan(temp) || isnan(hum)) { temp = 25.0; hum = 60.0; }

  // Default fallback demonstration values:
  temp = 24.5 + (sin(millis() / 5000.0) * 2.0);
  hum = 65.0 + (cos(millis() / 7000.0) * 3.0);
}

void loop() {
  // 1. Process incoming commands from Python Edge AI Dashboard
  if (Serial.available() > 0) {
    String cmd = Serial.readStringUntil('\n');
    cmd.trim();
    if (cmd.length() > 0) {
      // Basic JSON parsing or string matching for safety
      if (cmd.indexOf("\"pump\": 1") != -1 || cmd.indexOf("\"pump\":1") != -1) {
        setRelay(RELAY_PUMP, true);
      } else if (cmd.indexOf("\"pump\": 0") != -1 || cmd.indexOf("\"pump\":0") != -1) {
        setRelay(RELAY_PUMP, false);
      }

      if (cmd.indexOf("\"fan\": 1") != -1 || cmd.indexOf("\"fan\":1") != -1) {
        setRelay(RELAY_FAN, true);
      } else if (cmd.indexOf("\"fan\": 0") != -1 || cmd.indexOf("\"fan\":0") != -1) {
        setRelay(RELAY_FAN, false);
      }

      if (cmd.indexOf("\"light\": 1") != -1 || cmd.indexOf("\"light\":1") != -1) {
        setRelay(RELAY_LIGHT, true);
      } else if (cmd.indexOf("\"light\": 0") != -1 || cmd.indexOf("\"light\":0") != -1) {
        setRelay(RELAY_LIGHT, false);
      }
    }
  }

  // 2. Transmit Live Sensor Telemetry at scheduled interval
  unsigned long now = millis();
  if (now - lastTelemetryTime >= TELEMETRY_INTERVAL) {
    lastTelemetryTime = now;

    float temp = 0.0;
    float hum = 0.0;
    readDHT(temp, hum);
    float soil = readSoilMoisture();
    float lux = readLightLux();

    // Output JSON to Serial
    Serial.print("{\"temperature\": ");
    Serial.print(temp, 1);
    Serial.print(", \"humidity\": ");
    Serial.print(hum, 1);
    Serial.print(", \"soil_moisture\": ");
    Serial.print(soil, 1);
    Serial.print(", \"light_lux\": ");
    Serial.print(lux, 1);
    Serial.println("}");
  }
}
