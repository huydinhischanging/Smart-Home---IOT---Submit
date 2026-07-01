/**
 * ✅ MODULAR: WiFi Connection Handler
 * Manages WiFi connection with automatic reconnection
 */

#ifndef WIFI_HANDLER_H
#define WIFI_HANDLER_H

#include <WiFi.h>
#include <string>

class WiFiHandler {
private:
  const char* ssid;
  const char* password;
  unsigned long lastReconnectAttempt = 0;
  const unsigned long RECONNECT_INTERVAL = 5000;  // 5 seconds between retry attempts
  const int MAX_RETRIES = 20;  // Maximum retry attempts
  int connectionAttempts = 0;

public:
  WiFiHandler(const char* _ssid, const char* _password)
    : ssid(_ssid), password(_password) {}

  /**
   * Initialize WiFi connection
   * @return true if connected successfully
   */
  bool setup() {
    Serial.println("[WiFi] Starting WiFi connection...");
    WiFi.mode(WIFI_STA);
    WiFi.begin(ssid, password);

    int attempts = 0;
    while (WiFi.status() != WL_CONNECTED && attempts < 20) {
      delay(500);
      Serial.print(".");
      attempts++;
    }

    if (WiFi.status() == WL_CONNECTED) {
      Serial.println("\n[WiFi] ✅ Connected!");
      Serial.print("[WiFi] IP address: ");
      Serial.println(WiFi.localIP());
      return true;
    } else {
      Serial.println("\n[WiFi] ❌ Failed to connect");
      return false;
    }
  }

  /**
   * Maintain WiFi connection with automatic reconnection
   */
  void loop() {
    unsigned long now = millis();

    if (WiFi.status() != WL_CONNECTED) {
      if (now - lastReconnectAttempt > RECONNECT_INTERVAL) {
        lastReconnectAttempt = now;
        connectionAttempts++;

        if (connectionAttempts > MAX_RETRIES) {
          Serial.println("[WiFi] ⚠️  Max reconnection attempts reached");
          connectionAttempts = 0;
          ESP.restart();  // Restart if connection fails persistently
        } else {
          Serial.printf("[WiFi] Reconnecting... (attempt %d/%d)\n", connectionAttempts, MAX_RETRIES);
          WiFi.reconnect();
        }
      }
    } else {
      connectionAttempts = 0;  // Reset counter on successful connection
    }
  }

  /**
   * Check if WiFi is connected
   */
  bool isConnected() const {
    return WiFi.status() == WL_CONNECTED;
  }

  /**
   * Get WiFi status as string
   */
  const char* getStatusString() const {
    switch (WiFi.status()) {
      case WL_CONNECTED: return "Connected";
      case WL_NO_SSID_AVAIL: return "SSID not found";
      case WL_CONNECT_FAILED: return "Connection failed";
      case WL_DISCONNECTED: return "Disconnected";
      default: return "Unknown";
    }
  }
};

#endif // WIFI_HANDLER_H
