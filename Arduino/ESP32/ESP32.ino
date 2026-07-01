// ================================================================
// ESP32 — Smart Home for Elderly Care
// Project: IOT-SMARTHOME-ELDERLY
//
// Hardware specification: Huong_Dan_Su_Dung_ESP32_Board(1).docx
// Pin mapping verified against IOT_ESP32-OUTLET.SchDoc (Altium)
//
// MQTT Topics (matches Flask backend):
//   Subscribe : home/control/#          <- commands from backend/app
//   Publish   : home/status/{code}      -> device state feedback
//   Publish   : home/sensors/{code}     -> real-time sensor data
//
// Device codes (must match `code` column in MySQL `device` table):
//   den   -> light (Relay 1) — GPIO17 → Q1 transistor → RL1
//   quat  -> fan   (Relay 2) — GPIO16 → Q2 transistor → RL2
//
// Sensor codes:
//   temperature  -> DHT11 temperature (°C)  — GPIO15
//   humidity     -> DHT11 humidity (%)       — GPIO15
//   light        -> light sensor (0-100)     — GPIO32 (ADC1_CH4)
//   pir          -> PIR HC-SR501 ("DETECTED" | "CLEAR") — GPIO33
// ================================================================
// NOTE: Button pins (GPIO0/GPIO2) have external pull-up via R5/R6 (1kΩ).
// Per DOCX: "GPIO0/GPIO2 không có pull-up đủ mạnh" (internal pull-up weak),
// so the board provides external 1kΩ resistors (R5/R6) on P1/P2 connectors.
// ================================================================

#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <PubSubClient.h>
#include <DHT.h>
#include <Wire.h>
#include <LiquidCrystal_I2C.h>
#include <cstring>

#include "esp32_secrets.h"

#ifndef WIFI_SSID
#error "Create esp32_secrets.h from esp32_secrets.h.example and define Wi-Fi/MQTT credentials."
#endif

// ── WiFi ──────────────────────────────────────────────────────
const char* ssid     = WIFI_SSID;
const char* password = WIFI_PASSWORD;

// ── MQTT Broker (EMQX Cloud) ──────────────────────────────────
const char* mqttServer   = MQTT_SERVER;
const int   MQTT_PORT    = MQTT_PORT_VALUE;
const char* mqttUser     = MQTT_USER;
const char* mqttPassword = MQTT_PASSWORD;

// ── Device/Sensor code mapping (override in esp32_secrets.h) ───
// These codes must match `device.code` created on the web/backend.
#ifndef DEVICE_CODE_DEN
#define DEVICE_CODE_DEN "den"
#endif

#ifndef DEVICE_CODE_QUAT
#define DEVICE_CODE_QUAT "quat"
#endif

#ifndef SENSOR_CODE_TEMPERATURE
#define SENSOR_CODE_TEMPERATURE "temperature"
#endif

#ifndef SENSOR_CODE_HUMIDITY
#define SENSOR_CODE_HUMIDITY "humidity"
#endif

#ifndef SENSOR_CODE_LIGHT
#define SENSOR_CODE_LIGHT "light"
#endif

#ifndef SENSOR_CODE_PIR
#define SENSOR_CODE_PIR "pir"
#endif

// ================================================================
// PIN MAPPING — from Huong_Dan_Su_Dung_ESP32_Board(1).docx
// ================================================================
//
//  P6:  GPIO15  ← DHT11 data              (net: DHT11)
//  P7:  GPIO32  ← Light sensor ADC        (net: Light)   [ADC1_CH4, input-only]
//  P5:  GPIO33  ← PIR HC-SR501 motion    (net: PIR)     (5V supply, 30-60s warmup)
//  RL1: GPIO17  ← Relay 1 (den/light)    (net: Touch_1) via Q1 transistor
//  RL2: GPIO16  ← Relay 2 (quat/fan)     (net: Touch_2) via Q2 transistor
//  P1:  GPIO0   ← Button 1 (den toggle)  (net: Touch_in1) [ext. 1kΩ pull-up R5]
//  P2:  GPIO2   ← Button 2 (quat toggle) (net: Touch_in2) [ext. 1kΩ pull-up R6]
//       GPIO34  ← LED4 indicator (den)   (net: Led1)    [INPUT ONLY, no pull-up]
//       GPIO35  ← LED5 indicator (quat)  (net: Led2)    [INPUT ONLY, no pull-up]
//
// Standard I/O (not used by relays/sensors/buttons):
//  GPIO22  → I2C SCL                 (net: SCL)     → P breakout header
//  GPIO21  → I2C SDA                 (net: SDA)     → P breakout header
//  GPIO1   → UART TX                 (net: TX)      → UART header
//  GPIO3   → UART RX                 (net: RX)      → UART header
//  GPIO23  → SPI MOSI                (net: MOSI)    → SPI header
//  GPIO19  → SPI MISO                (net: MISO)    → SPI header
//  GPIO18  → SPI SCLK                (net: SCLK)    → SPI header
//  GPIO5   → SPI CS                  (net: CS)      → SPI header
//  GPIO4   → ADC breakout            (net: ADC)     → P13/P8 header
//
// ================================================================

// ── DHT11 ─────────────────────────────────────────────────────
#define DHT_PIN          15
#define DHTTYPE          DHT11

// ── I2C LCD (optional) ───────────────────────────────────────
#define I2C_SDA_PIN      21
#define I2C_SCL_PIN      22
#define LCD_I2C_ADDR     0x27
#define LCD_I2C_ADDR_ALT 0x3F
#define LCD_COLUMNS      16
#define LCD_ROWS         2

// ── Sensors ───────────────────────────────────────────────────
#define LIGHT_SENSOR_PIN 32    // ADC1_CH4 — LDR voltage divider, input-only
#define PIR_SENSOR_PIN   33    // PIR HC-SR501 signal pin
#define LIGHT_ADC_SAMPLES 16   // average to reduce ADC noise/spikes

// ── Relays (active-HIGH — transistor Q1/Q2 base driver) ───────
#define RELAY_DEN_PIN    17    // Relay 1 → light  (net: Touch_1 → Q1 → RL1)
#define RELAY_QUAT_PIN   16    // Relay 2 → fan    (net: Touch_2 → Q2 → RL2)

// ── Buttons (GPIO0/2 with external 1kΩ pull-up resistors) ────────
// Per DOCX: Internal pull-up insufficient; board provides R5/R6 (1kΩ) on P1/P2.
// Button press → pin goes LOW through P1/P2 connector.
// NOTE: GPIO0 is boot/flash pin (pressing briefly is safe).
// NOTE: GPIO2 must not be held LOW at boot (external pull-up prevents this).
#define BUTTON_DEN_PIN   0     // Button 1 → toggle den  (net: Touch_in1 → P1, ext. pull-up R5)
#define BUTTON_QUAT_PIN  2     // Button 2 → toggle quat (net: Touch_in2 → P2, ext. pull-up R6)

// ── LED indicators (INPUT ONLY pins — cannot be driven by GPIO) ──
// GPIO34 and GPIO35 are ADC input-only pins with no output capability.
// DOCX: LED4 and LED5 are driven externally via Led1/Led2 net in schematic.
// These pins can be read for diagnostics but do NOT digitalWrite or pinMode(OUTPUT).
#define LED_DEN_PIN      34    // LED4 — light status indicator  [INPUT ONLY, no pull-up]
#define LED_QUAT_PIN     35    // LED5 — fan status indicator    [INPUT ONLY, no pull-up]

// ── Sensor publish interval ───────────────────────────────────
#define SENSOR_INTERVAL  5000  // ms between DHT11 + light publishes

// ── Objects ───────────────────────────────────────────────────
DHT              dht(DHT_PIN, DHTTYPE);
LiquidCrystal_I2C lcd27(LCD_I2C_ADDR, LCD_COLUMNS, LCD_ROWS);
LiquidCrystal_I2C lcd3f(LCD_I2C_ADDR_ALT, LCD_COLUMNS, LCD_ROWS);
LiquidCrystal_I2C* lcd = nullptr;
WiFiClientSecure espClient;
PubSubClient     client(espClient);

unsigned long lastReconnectAttempt = 0;
bool mqttTlsReady = false;
bool lcdReady = false;

// ── Relay state cache (to support button toggle) ──────────────
static bool relayDenState  = false;
static bool relayQuatState = false;

// ── LCD state cache (avoid flicker + keep latest values) ──────
static float lastTemperature = NAN;
static float lastHumidity    = NAN;
static int   lastLightLevel  = -1;
static bool  lastPirDetected = false;

// ── Forward declarations ──────────────────────────────────────
void mqttCallback(char* topic, byte* message, unsigned int length);
void reconnect();
void handleButtons();
void handleSensors(unsigned long now);
void setupWiFi();
void publishStatus(const char* deviceCode, const char* payload);
void publishSensor(const char* sensorCode, const String& payload, bool retain = true);
void setRelay(uint8_t pin, bool& stateVar, const char* deviceCode, bool on);
void updateLcd(unsigned long now);
void lcdPrintLine(uint8_t row, const String& text);

// =============================================================
// SETUP
// =============================================================
void setup() {
  Serial.begin(115200);

  // ── Optional I2C LCD on GPIO21/22 (safe if not installed yet) ──
  Wire.begin(I2C_SDA_PIN, I2C_SCL_PIN);
  delay(80);  // Let backpack power stabilize before probing.

  Wire.beginTransmission(LCD_I2C_ADDR);
  if (Wire.endTransmission() == 0) {
    lcd = &lcd27;
    lcd->init();
    Wire.setClock(100000);  // re-set after init() because library calls Wire.begin() internally which resets clock
    lcd->backlight();
    lcd->clear();
    lcdPrintLine(0, "SmartHome Elder");
    lcdPrintLine(1, "Booting...");
    lcdReady = true;
    Serial.println("[SETUP] LCD detected at I2C 0x27");
  } else {
    Wire.beginTransmission(LCD_I2C_ADDR_ALT);
    if (Wire.endTransmission() == 0) {
      lcd = &lcd3f;
      lcd->init();
      Wire.setClock(100000);  // same reason as above
      lcd->backlight();
      lcd->clear();
      lcdPrintLine(0, "SmartHome Elder");
      lcdPrintLine(1, "Booting...");
      lcdReady = true;
      Serial.println("[SETUP] LCD detected at I2C 0x3F");
    } else {
      Serial.println("[SETUP] LCD not detected at I2C 0x27/0x3F (firmware continues normally)");
    }
  }

  // ── Relay outputs (active-HIGH, GPIO17/16 drive transistor bases) ──
  // Default OFF state (LOW) to prevent spurious relay triggers.
  pinMode(RELAY_DEN_PIN,   OUTPUT); digitalWrite(RELAY_DEN_PIN,   LOW);
  pinMode(RELAY_QUAT_PIN,  OUTPUT); digitalWrite(RELAY_QUAT_PIN,  LOW);
  Serial.println("[SETUP] Relay outputs initialized (GPIO17, GPIO16)");

  // ── Sensor inputs ────────────────────────────────────────
  // GPIO33 (PIR): Use INPUT_PULLDOWN to avoid floating HIGH when sensor disconnected.
  // HC-SR501 drives signal HIGH on motion detection (active-high output).
  pinMode(PIR_SENSOR_PIN, INPUT_PULLDOWN);
  
  // GPIO32 (Light sensor ADC): Configure 12-bit resolution + 11dB attenuation.
  // 11dB attenuation allows up to ~3.6V on 3.3V GPIO (safety margin for 5V divider circuit).
  analogReadResolution(12);                                    // 0-4095 raw values
  analogSetPinAttenuation(LIGHT_SENSOR_PIN, ADC_11db);        // Safe range for LDR divider
  Serial.println("[SETUP] ADC configured: 12-bit, 11dB attenuation (GPIO32)");

  // ── Button inputs (GPIO0/2 with external 1kΩ pull-up R5/R6) ─────────
  // Per DOCX, internal pull-up insufficient; board provides external resistors.
  // Use INPUT (not INPUT_PULLUP) to avoid conflicting with external R5/R6.
  // Button press pulls pin LOW (active-low, reads via readStableLOW()).
  pinMode(BUTTON_DEN_PIN,  INPUT);
  pinMode(BUTTON_QUAT_PIN, INPUT);
  Serial.println("[SETUP] Button inputs configured (GPIO0 with R5, GPIO2 with R6)");

  // ── LED indicator pins: INPUT ONLY (GPIO34/35 no output capability) ─
  // DOCX: LED4 and LED5 are driven externally via Led1/Led2 net.
  // GPIO34 and GPIO35 cannot sink/source current (input-only, no pull-up).
  // These pins are read-only for diagnostics; do NOT digitalWrite.
  pinMode(LED_DEN_PIN,  INPUT);
  pinMode(LED_QUAT_PIN, INPUT);
  Serial.println("[SETUP] LED indicators set to input-only (GPIO34, GPIO35)");

  dht.begin();
  setupWiFi();

  // ── TLS configuration ────────────────────────────────────
  if (MQTT_USE_CA_CERT && std::strlen(MQTT_ROOT_CA) > 0) {
    espClient.setCACert(MQTT_ROOT_CA);
    mqttTlsReady = true;
    Serial.println("[OK] MQTT TLS: CA certificate pinning enabled (secure)");
  } else if (MQTT_ALLOW_INSECURE_TLS) {
    #warning "MQTT_ALLOW_INSECURE_TLS is enabled — certificate verification DISABLED!"
    #warning "FOR DEVELOPMENT ONLY. Do NOT deploy to production with this setting!"
    espClient.setInsecure();
    mqttTlsReady = true;
    Serial.println("[WARN] MQTT TLS: Insecure mode (dev only — MITM risk)");
  } else {
    Serial.println("[ERROR] MQTT TLS not configured. Halting.");
    Serial.println("[ERROR] Set MQTT_USE_CA_CERT=1 + MQTT_ROOT_CA, or MQTT_ALLOW_INSECURE_TLS=1 (dev only).");
    while (true) delay(1000);
  }

  client.setServer(mqttServer, MQTT_PORT);
  client.setCallback(mqttCallback);
}

// =============================================================
// LOOP
// =============================================================
void loop() {
  unsigned long now = millis();

  static unsigned long lastWifiRetry = 0;
  wl_status_t wifiStatus = WiFi.status();
  if (wifiStatus != WL_CONNECTED && wifiStatus != WL_IDLE_STATUS) {
    if (lastWifiRetry == 0 || (now - lastWifiRetry) > 10000UL) {
      lastWifiRetry = now;
      Serial.println("[WIFI] Disconnected. Triggering reconnect...");
      WiFi.reconnect();
    }
  }

  if (!client.connected()) {
    if (lastReconnectAttempt == 0 || (now - lastReconnectAttempt) > 5000) {
      lastReconnectAttempt = now;
      reconnect();
    }
  } else {
    client.loop();
  }

  handleSensors(now);
  handleButtons();
  updateLcd(now);
}

// =============================================================
// WIFI
// =============================================================
void setupWiFi() {
  WiFi.mode(WIFI_STA);
  WiFi.setAutoReconnect(true);
  WiFi.persistent(true);

  Serial.printf("Connecting to WiFi: %s\n", ssid);
  WiFi.begin(ssid, password);

  // Do not block forever during network outages; loop() will retry.
  unsigned long startAttempt = millis();
  while (WiFi.status() != WL_CONNECTED && (millis() - startAttempt) < 20000UL) {
    delay(500);
    Serial.print(".");
  }

  if (WiFi.status() == WL_CONNECTED) {
    Serial.printf("\nWiFi connected. IP: %s\n", WiFi.localIP().toString().c_str());
  } else {
    Serial.println("\n[WIFI] Initial connect timeout. Will retry in loop().");
  }
}

// =============================================================
// MQTT — RECONNECT
// =============================================================
void reconnect() {
  if (!mqttTlsReady) {
    Serial.println("[MQTT] TLS not ready — skipping connect.");
    return;
  }

  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("[MQTT] WiFi not connected — skipping MQTT connect.");
    return;
  }

  Serial.print("Connecting to MQTT broker... ");
  String clientId = "ESP32_Elderly_" + WiFi.macAddress();

  if (client.connect(clientId.c_str(), mqttUser, mqttPassword)) {
    Serial.println("connected!");
    client.subscribe("home/control/#");
    Serial.println("Subscribed: home/control/#");

    // Publish current relay states on reconnect so backend stays in sync
    publishStatus(DEVICE_CODE_DEN,  relayDenState  ? "ON" : "OFF");
    publishStatus(DEVICE_CODE_QUAT, relayQuatState ? "ON" : "OFF");
  } else {
    Serial.printf("failed, rc=%d — retry in 5s\n", client.state());
  }
}

// =============================================================
// MQTT — RECEIVE COMMANDS FROM BACKEND
//   Topic  : home/control/{device_code}
//         or home/control/{device_type}/{device_code}
//   Payload: "ON" | "OFF"
// =============================================================
void mqttCallback(char* topic, byte* message, unsigned int length) {
  String msg;
  msg.reserve(length);
  for (unsigned int i = 0; i < length; i++) msg += (char)message[i];
  msg.trim();
  Serial.printf("[MQTT IN] %s -> %s\n", topic, msg.c_str());

  String topicStr = String(topic);
  int lastSlash = topicStr.lastIndexOf('/');
  if (lastSlash < 0) {
    Serial.printf("[MQTT] Invalid control topic: %s\n", topic);
    return;
  }

  String devCode = topicStr.substring(lastSlash + 1);
  String topicPrefix = topicStr.substring(0, lastSlash);
  String topicType = "";
  int secondLastSlash = topicPrefix.lastIndexOf('/');
  if (secondLastSlash >= 0 && topicPrefix.substring(0, secondLastSlash).equalsIgnoreCase("home/control")) {
    topicType = topicPrefix.substring(secondLastSlash + 1);
  }

  devCode.toLowerCase();
  topicType.toLowerCase();

  bool parsedOk = false;
  bool turnOn = false;

  if (msg.equalsIgnoreCase("ON")) {
    turnOn = true;
    parsedOk = true;
  } else if (msg.equalsIgnoreCase("OFF")) {
    turnOn = false;
    parsedOk = true;
  } else {
    char* endPtr = nullptr;
    float numericValue = strtof(msg.c_str(), &endPtr);
    if (endPtr != msg.c_str() && *endPtr == '\0') {
      turnOn = numericValue > 0.0f;
      parsedOk = true;
      Serial.printf("[MQTT] Numeric command for %s: %.2f -> %s\n", devCode.c_str(), numericValue, turnOn ? "ON" : "OFF");
    }
  }

  if (!parsedOk) {
    Serial.printf("[MQTT] Unsupported payload '%s' on topic %s\n", msg.c_str(), topic);
    return;
  }

  if (!topicType.isEmpty()) {
    Serial.printf("[MQTT] V2 control topic type=%s code=%s\n", topicType.c_str(), devCode.c_str());
  }

  if      (devCode == DEVICE_CODE_DEN)  setRelay(RELAY_DEN_PIN,  relayDenState,  DEVICE_CODE_DEN,  turnOn);
  else if (devCode == DEVICE_CODE_QUAT) setRelay(RELAY_QUAT_PIN, relayQuatState, DEVICE_CODE_QUAT, turnOn);
  else Serial.printf("[MQTT] Unknown device code: %s\n", devCode.c_str());
}

// =============================================================
// HELPER — SET RELAY + UPDATE STATE CACHE + PUBLISH FEEDBACK
// =============================================================
void setRelay(uint8_t pin, bool& stateVar, const char* deviceCode, bool on) {
  digitalWrite(pin, on ? HIGH : LOW);
  stateVar = on;
  publishStatus(deviceCode, on ? "ON" : "OFF");
  Serial.printf("[RELAY] %s -> %s\n", deviceCode, on ? "ON" : "OFF");
}

void publishStatus(const char* deviceCode, const char* payload) {
  if (!client.connected()) return;
  char topic[96];
  snprintf(topic, sizeof(topic), "home/status/%s", deviceCode);
  client.publish(topic, payload, true);
}

void publishSensor(const char* sensorCode, const String& payload, bool retain) {
  if (!client.connected()) return;
  char topic[96];
  snprintf(topic, sizeof(topic), "home/sensors/%s", sensorCode);
  client.publish(topic, payload.c_str(), retain);
}

void lcdPrintLine(uint8_t row, const String& text) {
  if (!lcdReady || lcd == nullptr || row >= LCD_ROWS) return;

  String padded = text;
  if (padded.length() > LCD_COLUMNS) {
    padded.remove(LCD_COLUMNS);
  }
  while (padded.length() < LCD_COLUMNS) {
    padded += ' ';
  }

  lcd->setCursor(0, row);
  lcd->print(padded);
}

void updateLcd(unsigned long now) {
  if (!lcdReady) return;

  static unsigned long lastLcdRefresh = 0;
  if (now - lastLcdRefresh < 1000) return;
  lastLcdRefresh = now;

  String line1;
  if (isnan(lastTemperature) || isnan(lastHumidity)) {
    line1 = "T:--.- H:--.-";
  } else {
    line1 = "T:" + String(lastTemperature, 1) + " H:" + String(lastHumidity, 0);
  }

  static bool showStatusPage = false;
  showStatusPage = !showStatusPage;

  if (!showStatusPage) {
    String pirText = lastPirDetected ? "MOV" : "CLR";
    String lightText = (lastLightLevel >= 0) ? String(lastLightLevel) : String("--");
    lcdPrintLine(0, line1);
    lcdPrintLine(1, "L:" + lightText + " PIR:" + pirText);
    return;
  }

  String wifiText = (WiFi.status() == WL_CONNECTED) ? "OK" : "NO";
  String mqttText = client.connected() ? "OK" : "NO";
  String relayText = String("D:") + (relayDenState ? "ON" : "OFF") + " Q:" + (relayQuatState ? "ON" : "OFF");

  lcdPrintLine(0, "Wi:" + wifiText + " MQ:" + mqttText);
  lcdPrintLine(1, relayText);
}

// =============================================================
// BUTTONS — PHYSICAL TOGGLE (GPIO0 / GPIO2)
//
// P1:  GPIO0  ← Touch_in1 → Button 1 (den/light)  [ext. pull-up R5 1kΩ]
// P2:  GPIO2  ← Touch_in2 → Button 2 (quat/fan)   [ext. pull-up R6 1kΩ]
//
// Button press → pin goes LOW (active-low logic).
//
// Hardware notes from DOCX:
//   - "GPIO0/GPIO2 không có pull-up đủ mạnh" → external R5/R6 needed
//   - R5 (GPIO0 pull-up): Supports 3.3V logic without exceeding GPIO rating
//   - R6 (GPIO2 pull-up): Same as R5
//   - Button closes to GND when pressed
//   - Voltage divider design ensures 3.3V GPIO-safe signal
//
// ESP32 bootstrap pin behavior:
//   - GPIO0 LOW at boot → enters flash/download mode (safe; returns to normal operation)
//   - GPIO2 LOW at boot → some variants enter download mode (but R6 pull-up prevents this)
// =============================================================
// Button press detection uses readStableLOW() to debounce.
// =============================================================

// Read a pin LOW reliably: sample 5 times to filter floating noise
// on input-only pins with no internal pull-up.
bool readStableLOW(uint8_t pin) {
  for (int i = 0; i < 5; i++) {
    if (digitalRead(pin) != LOW) return false;
    delayMicroseconds(200);
  }
  return true;
}

void handleButtons() {
  // Ignore button presses for the first 2s after boot.
  // GPIO0/GPIO2 can read LOW during ESP32 boot strapping, which would
  // falsely trigger relays before the user touches anything.
  if (millis() < 2000UL) return;

  const unsigned long DEBOUNCE = 200;  // ms

  // ── Button 1: toggle den (light) ─────────────────────────
  static bool pressed1 = false;
  static unsigned long t1 = 0;
  bool cur1 = readStableLOW(BUTTON_DEN_PIN);
  if (cur1 && !pressed1 && (millis() - t1) > DEBOUNCE) {
    t1 = millis();
    pressed1 = true;
    setRelay(RELAY_DEN_PIN, relayDenState, DEVICE_CODE_DEN, !relayDenState);
  }
  if (!cur1) pressed1 = false;

  // ── Button 2: toggle quat (fan) ──────────────────────────
  static bool pressed2 = false;
  static unsigned long t2 = 0;
  bool cur2 = readStableLOW(BUTTON_QUAT_PIN);
  if (cur2 && !pressed2 && (millis() - t2) > DEBOUNCE) {
    t2 = millis();
    pressed2 = true;
    setRelay(RELAY_QUAT_PIN, relayQuatState, DEVICE_CODE_QUAT, !relayQuatState);
  }
  if (!cur2) pressed2 = false;
}

// =============================================================
// SENSORS — READ AND PUBLISH (periodic + on-change for PIR)
//
//   home/sensors/temperature and home/sensors/temperature/{code}
//   home/sensors/humidity and home/sensors/humidity/{code}
//   home/sensors/light and home/sensors/light/{code}
//   home/sensors/pir and home/sensors/motion/{code}
//
// Temperature/Humidity (DHT11 on P6, GPIO15):
//   Reads both temperature (°C) and humidity (%) in one call.
//   Published every 5 seconds to home/sensors/{temperature,humidity}.
//
// Light sensor circuit (P7 connector, GPIO32):
//   Circuit: 5V → LDR → Vout(GPIO32) → 10kΩ R → GND
//   On this board, observed behavior is inverted at GPIO32:
//   Bright: ADC raw tends to be lower  -> map to higher lightLevel
//   Dark  : ADC raw tends to be higher -> map to lower lightLevel
//   ADC configured: 12-bit (0-4095 raw), 11dB attenuation, 16-sample averaging.
//
// PIR motion sensor (P5 connector, GPIO33, HC-SR501):
//   5V supply, 30-60s warmup time recommended after power-on (per DOCX).
//   Output: HIGH when motion detected, LOW when clear (active-high).
//   GPIO33 pulldown prevents false triggers when sensor disconnected.
//   Publishes to home/sensors/pir only when state changes (efficient).
// =============================================================
void handleSensors(unsigned long now) {

  lastPirDetected = (digitalRead(PIR_SENSOR_PIN) == HIGH);

  // ── Periodic: DHT11 + light sensor ───────────────────────
  static unsigned long lastSend = 0;
  if (now - lastSend >= SENSOR_INTERVAL) {
    lastSend = now;

    if (!client.connected()) return;

    // DHT11 — temperature & humidity
    float temp  = dht.readTemperature();
    float humid = dht.readHumidity();

    if (!isnan(temp)) {
      lastTemperature = temp;
      publishSensor(SENSOR_CODE_TEMPERATURE, String(temp, 1), true);
      Serial.printf("[SENSOR] %s=%.1f°C\n", SENSOR_CODE_TEMPERATURE, temp);
    } else {
      Serial.println("[SENSOR] DHT11 temperature read failed");
    }

    if (!isnan(humid)) {
      lastHumidity = humid;
      publishSensor(SENSOR_CODE_HUMIDITY, String(humid, 1), true);
      Serial.printf("[SENSOR] %s=%.1f%%\n", SENSOR_CODE_HUMIDITY, humid);
    } else {
      Serial.println("[SENSOR] DHT11 humidity read failed");
    }

    // Light sensor (LDR voltage divider on GPIO32 / ADC1_CH4)
    // Raw: 0-4095 (12-bit ADC). Board behavior is inverted:
    // bright -> lower raw, dark -> higher raw.
    long rawSum = 0;
    for (int i = 0; i < LIGHT_ADC_SAMPLES; i++) {
      rawSum += analogRead(LIGHT_SENSOR_PIN);
      delay(2);
    }
    int raw        = (int)(rawSum / LIGHT_ADC_SAMPLES);
    int lightLevel = constrain(map(raw, 4095, 0, 0, 100), 0, 100);
    lastLightLevel = lightLevel;
    publishSensor(SENSOR_CODE_LIGHT, String(lightLevel), true);
    Serial.printf("[SENSOR] %s=%d/100 (raw=%d)\n", SENSOR_CODE_LIGHT, lightLevel, raw);

    if (raw >= 4080) {
      Serial.println("[WARN] light raw near ADC max. Check wiring: sensor A0->GPIO32, GND common, use 3.3V (not 5V) for ESP32 ADC.");
    }
  }

  // ── PIR: publish only on state change ────────────────────
  // GPIO33 — HIGH = motion detected, LOW = clear
  static String lastPir = "";
  String curPir = lastPirDetected ? "DETECTED" : "CLEAR";
  if (curPir != lastPir) {
    lastPir = curPir;
    if (client.connected()) {
      publishSensor(SENSOR_CODE_PIR, curPir, true);
      Serial.printf("[SENSOR] %s=%s\n", SENSOR_CODE_PIR, curPir.c_str());
    }
  }
}
