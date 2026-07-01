/**
 * ✅ MODULAR: Sensor Data Collection Handler
 * Manages DHT, light sensor, and PIR motion sensor readings
 */

#ifndef SENSOR_HANDLER_H
#define SENSOR_HANDLER_H

#include <DHT.h>
#include <string>

struct SensorReading {
  float temperature = 0.0f;
  float humidity = 0.0f;
  float lightLevel = 0.0f;
  bool motionDetected = false;
  unsigned long lastUpdate = 0;
};

class SensorHandler {
private:
  DHT dht;
  int lightSensorPin;
  int pirSensorPin;
  unsigned long lastSensorUpdate = 0;
  const unsigned long SENSOR_INTERVAL = 5000;  // 5 seconds

  // Sensor value caching to avoid duplicate readings
  SensorReading lastReading;
  const float TEMP_THRESHOLD = 0.5f;  // Only update if change > 0.5°C
  const int LIGHT_THRESHOLD = 10;     // Only update if change > 10 units

public:
  SensorHandler(uint8_t dhtPin, uint8_t dhtType, uint8_t _lightPin, uint8_t _pirPin)
    : dht(dhtPin, dhtType), lightSensorPin(_lightPin), pirSensorPin(_pirPin) {}

  /**
   * Initialize sensors
   */
  void setup() {
    Serial.println("[Sensors] Initializing...");

    dht.begin();
    pinMode(lightSensorPin, INPUT);
    pinMode(pirSensorPin, INPUT);

    Serial.println("[Sensors] ✅ Initialized");
  }

  /**
   * Read all sensor values (call in main loop with SENSOR_INTERVAL)
   * @return SensorReading with current sensor values
   */
  SensorReading read() {
    unsigned long now = millis();

    // Rate limiting: only read sensors at specified interval
    if (now - lastSensorUpdate < SENSOR_INTERVAL) {
      return lastReading;
    }

    lastSensorUpdate = now;
    SensorReading reading;
    reading.lastUpdate = now;

    // ✅ Read DHT sensor (temperature + humidity)
    if (readDHT(reading)) {
      logDHTReading(reading);
    } else {
      Serial.println("[DHT] ⚠️  Read failed");
    }

    // ✅ Read light sensor
    reading.lightLevel = readLightSensor();
    if (abs(reading.lightLevel - lastReading.lightLevel) > LIGHT_THRESHOLD) {
      Serial.printf("[Light] %d (changed from %.0f)\n", (int)reading.lightLevel, lastReading.lightLevel);
    }

    // ✅ Read PIR motion sensor
    reading.motionDetected = readPIR();
    if (reading.motionDetected != lastReading.motionDetected) {
      Serial.printf("[PIR] Motion %s\n", reading.motionDetected ? "detected" : "stopped");
    }

    lastReading = reading;
    return reading;
  }

  /**
   * Get last read sensor values (non-blocking)
   */
  SensorReading getLastReading() const {
    return lastReading;
  }

  /**
   * Format sensor reading as JSON for MQTT publishing
   */
  String readingToJson(const SensorReading& reading) {
    char json[256];
    snprintf(json, sizeof(json),
             "{\"temperature\":%.2f,\"humidity\":%.2f,\"light_level:%d,\"motion\":%s,\"timestamp\":%lu}",
             reading.temperature, reading.humidity, (int)reading.lightLevel,
             reading.motionDetected ? "true" : "false", reading.lastUpdate);
    return String(json);
  }

private:
  /**
   * Read DHT11 temperature and humidity sensor
   */
  bool readDHT(SensorReading& reading) {
    float temp = dht.readTemperature();
    float humidity = dht.readHumidity();

    if (isnan(temp) || isnan(humidity)) {
      return false;
    }

    // Only update if significant change
    if (abs(temp - lastReading.temperature) > TEMP_THRESHOLD) {
      reading.temperature = temp;
    } else {
      reading.temperature = lastReading.temperature;
    }

    if (abs(humidity - lastReading.humidity) > TEMP_THRESHOLD) {
      reading.humidity = humidity;
    } else {
      reading.humidity = lastReading.humidity;
    }

    return true;
  }

  /**
   * Log DHT reading
   */
  void logDHTReading(const SensorReading& reading) {
    Serial.printf("[DHT] Temperature: %.2f°C, Humidity: %.2f%%\n",
                  reading.temperature, reading.humidity);
  }

  /**
   * Read light sensor (0-4095 from ADC)
   */
  float readLightSensor() {
    int rawValue = analogRead(lightSensorPin);
    // Convert 0-4095 to 0-100 percentage
    return (rawValue / 4095.0) * 100.0f;
  }

  /**
   * Read PIR motion sensor
   */
  bool readPIR() {
    return digitalRead(pirSensorPin) == HIGH;
  }
};

#endif // SENSOR_HANDLER_H
