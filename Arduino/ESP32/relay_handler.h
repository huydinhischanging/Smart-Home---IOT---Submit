/**
 * ✅ MODULAR: Relay Control Handler
 * Manages relay switching for devices (lights, fans, etc.)
 */

#ifndef RELAY_HANDLER_H
#define RELAY_HANDLER_H

#include <string>
#include <map>

struct RelayDevice {
  uint8_t pin;
  const char* code;
  const char* name;
  bool isActive;  // Current state
  unsigned long lastControl = 0;

  RelayDevice(uint8_t _pin, const char* _code, const char* _name)
    : pin(_pin), code(_code), name(_name), isActive(false) {}
};

class RelayHandler {
private:
  std::map<String, RelayDevice*> devices;
  const unsigned long CONTROL_DEBOUNCE = 100;  // Prevent rapid switching

public:
  /**
   * Register a relay device
   */
  void addDevice(uint8_t pin, const char* code, const char* name) {
    RelayDevice* device = new RelayDevice(pin, code, name);
    devices[String(code)] = device;

    pinMode(pin, OUTPUT);
    digitalWrite(pin, LOW);  // Start in OFF state

    Serial.printf("[Relay] Registered: %s (%s) on pin %d\n", name, code, pin);
  }

  /**
   * Initialize all relays
   */
  void setup() {
    Serial.printf("[Relays] Initializing %d devices\n", devices.size());
    // All device initialization handled in addDevice()
  }

  /**
   * Control a relay device
   * @param deviceCode Code of the device to control
   * @param action "ON" or "OFF"
   * @return true if successful
   */
  bool control(const char* deviceCode, const char* action) {
    String code(deviceCode);
    if (devices.find(code) == devices.end()) {
      Serial.printf("[Relay] ❌ Unknown device: %s\n", deviceCode);
      return false;
    }

    RelayDevice* device = devices[code];
    unsigned long now = millis();

    // Debounce check
    if (now - device->lastControl < CONTROL_DEBOUNCE) {
      Serial.printf("[Relay] ⚠️  Debouncing: %s\n", deviceCode);
      return false;
    }

    String actionUpper(action);
    actionUpper.toUpperCase();

    bool shouldActivate = false;
    if (actionUpper == "ON") {
      shouldActivate = true;
    } else if (actionUpper == "OFF") {
      shouldActivate = false;
    } else {
      Serial.printf("[Relay] ⚠️  Unknown action: %s\n", action);
      return false;
    }

    return setRelayState(device, shouldActivate);
  }

  /**
   * Toggle a relay device
   */
  bool toggle(const char* deviceCode) {
    String code(deviceCode);
    if (devices.find(code) == devices.end()) {
      return false;
    }

    RelayDevice* device = devices[code];
    return setRelayState(device, !device->isActive);
  }

  /**
   * Get device state
   */
  bool getState(const char* deviceCode) {
    String code(deviceCode);
    if (devices.find(code) == devices.end()) {
      return false;
    }
    return devices[code]->isActive;
  }

  /**
   * Get device state as string (ON/OFF)
   */
  const char* getStateString(const char* deviceCode) {
    return getState(deviceCode) ? "ON" : "OFF";
  }

  /**
   * Get all device states as JSON
   */
  String getAllStatesJson() {
    String json = "{\"devices\":[";
    bool first = true;

    for (auto& pair : devices) {
      RelayDevice* device = pair.second;

      if (!first) json += ",";
      first = false;

      char deviceJson[128];
      snprintf(deviceJson, sizeof(deviceJson),
               "{\"code\":\"%s\",\"name\":\"%s\",\"state\":\"%s\"}",
               device->code, device->name, device->isActive ? "ON" : "OFF");
      json += deviceJson;
    }

    json += "]}";
    return json;
  }

private:
  /**
   * Set relay to specific state with safety checks
   */
  bool setRelayState(RelayDevice* device, bool shouldActivate) {
    // Prevent rapid switching
    unsigned long now = millis();
    if (now - device->lastControl < CONTROL_DEBOUNCE) {
      Serial.printf("[Relay] ⚠️  Too fast: %s\n", device->code);
      return false;
    }

    device->lastControl = now;

    // Only act if state is changing
    if (device->isActive == shouldActivate) {
      Serial.printf("[Relay] ℹ️  Already %s: %s\n",
                    shouldActivate ? "ON" : "OFF", device->code);
      return true;
    }

    // ✅ Safety: Validate pin is in range
    if (device->pin < 0 || device->pin > 39) {  // ESP32 pins
      Serial.printf("[Relay] ❌ Invalid pin: %d\n", device->pin);
      return false;
    }

    // Apply control
    // Note: Active-high relay (LOW=OFF, HIGH=ON)
    // For active-low relay, invert: digitalWrite(device->pin, shouldActivate ? LOW : HIGH)
    digitalWrite(device->pin, shouldActivate ? HIGH : LOW);
    device->isActive = shouldActivate;

    Serial.printf("[Relay] ✅ Switched %s: %s\n",
                  device->code, shouldActivate ? "ON" : "OFF");
    return true;
  }
};

#endif // RELAY_HANDLER_H
